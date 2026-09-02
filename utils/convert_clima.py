import pandas as pd
import os

def convert_excel_to_parquet():
    excel_path = "data/ClimaHisto.xlsx"
    parquet_path = "data/ClimaHisto.parquet"
    
    print(f"Reading {excel_path}...")
    try:
        df = pd.read_excel(excel_path)
        
        # Ensure date column is datetime
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'])
            
        print(f"Converting to {parquet_path}...")
        df.to_parquet(parquet_path, index=False)
        print("Conversion successful!")
        
    except Exception as e:
        print(f"Error during conversion: {e}")

if __name__ == "__main__":
    convert_excel_to_parquet()
