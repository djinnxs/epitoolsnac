import os
import shutil
import numpy as np
import pandas as pd
from datetime import datetime
from meteostat import daily, stations, config

def update_clima():
    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parquet_path = os.path.join(base_dir, 'data', 'ClimaHisto.parquet')
    backup_path = os.path.join(base_dir, 'data', 'ClimaHisto_backup.parquet')
    
    # 1. Back up original parquet file
    if not os.path.exists(backup_path):
        print(f"Creating backup: {backup_path}")
        shutil.copyfile(parquet_path, backup_path)
    else:
        print(f"Backup already exists: {backup_path}")
        
    # 2. Load original parquet
    print("Loading original parquet...")
    df_old = pd.read_parquet(parquet_path)
    df_old['Fecha'] = pd.to_datetime(df_old['Fecha'])
    
    # Map for stations to preserve exactly 'Estación' and 'PROVINCIA' names
    station_mapping = df_old[['CodEstacion', 'Estación', 'PROVINCIA']].drop_duplicates().set_index('CodEstacion').to_dict('index')
    
    # 3. Query Meteostat to check valid stations
    print("Checking valid stations in Meteostat...")
    config.block_large_requests = False
    old_ids = df_old['CodEstacion'].unique()
    old_ids_str = [str(x).zfill(5) for x in old_ids]
    place_holders = ', '.join(["'" + x + "'" for x in old_ids_str])
    
    df_meteo = stations.query(f"SELECT id FROM stations WHERE id IN ({place_holders})")
    matched_ids_str = df_meteo['id'].tolist()
    matched_ids_int = [int(x) for x in matched_ids_str]
    
    print(f"Total stations in parquet: {len(old_ids)}")
    print(f"Stations found in Meteostat: {len(matched_ids_str)}")
    print(f"Stations missing in Meteostat: {len(old_ids) - len(matched_ids_str)}")
    
    # 4. Fetch daily data for matched stations from 2024-01-01 to today
    start = datetime(2024, 1, 1)
    end = datetime.today()
    print(f"Fetching Meteostat data from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}...")
    data = daily(matched_ids_str, start, end)
    df_new_raw = data.fetch()
    
    if df_new_raw.empty:
        print("No new data was fetched. Aborting update.")
        return
        
    df_new_raw = df_new_raw.reset_index()
    
    # 5. Format new data
    print("Formatting new data...")
    df_new_raw['CodEstacion'] = df_new_raw['station'].astype(int)
    df_new_raw['Fecha'] = pd.to_datetime(df_new_raw['time'])
    
    # Map 'Estación' and 'PROVINCIA' names from original mapping
    df_new_raw['Estación'] = df_new_raw['CodEstacion'].map(lambda x: station_mapping.get(x, {}).get('Estación', ''))
    df_new_raw['PROVINCIA'] = df_new_raw['CodEstacion'].map(lambda x: station_mapping.get(x, {}).get('PROVINCIA', ''))
    
    # Format columns to match old structure + 'Precipitación (mm)'
    df_new = pd.DataFrame({
        'CodEstacion': df_new_raw['CodEstacion'],
        'Fecha': df_new_raw['Fecha'],
        'Temp. Maxima (°C)': df_new_raw['tmax'].round(1),
        'Temp. Minima (°C)': df_new_raw['tmin'].round(1),
        'Precipitación (mm)': df_new_raw['prcp'].fillna(0.0).round(1),
        'Estación': df_new_raw['Estación'],
        'PROVINCIA': df_new_raw['PROVINCIA']
    })
    
    # 6. Filter old data
    print("Preparing old dataset...")
    # Convert temperature columns in old data to float64
    df_old['Temp. Maxima (°C)'] = pd.to_numeric(df_old['Temp. Maxima (°C)'], errors='coerce')
    df_old['Temp. Minima (°C)'] = pd.to_numeric(df_old['Temp. Minima (°C)'], errors='coerce')
    
    # Add 'Precipitación (mm)' column to old data (set as NaN for historical)
    df_old['Precipitación (mm)'] = np.nan
    
    # Delete data from 2024-01-01 onwards for the matched stations
    mask_to_delete = (df_old['Fecha'] >= '2024-01-01') & (df_old['CodEstacion'].isin(matched_ids_int))
    df_old_kept = df_old[~mask_to_delete].copy()
    
    # 7. Concatenate old and new data
    print("Combining datasets...")
    df_final = pd.concat([df_old_kept, df_new], ignore_index=True)
    
    # 8. Sort and save
    df_final = df_final.sort_values(['CodEstacion', 'Fecha']).reset_index(drop=True)
    
    # Ensure correct columns order
    cols_order = ['CodEstacion', 'Fecha', 'Temp. Maxima (°C)', 'Temp. Minima (°C)', 'Precipitación (mm)', 'Estación', 'PROVINCIA']
    df_final = df_final[cols_order]
    
    print(f"Final dataset shape: {df_final.shape}")
    print(f"Saving to {parquet_path}...")
    df_final.to_parquet(parquet_path, index=False)
    print("Update completed successfully!")

if __name__ == "__main__":
    update_clima()
