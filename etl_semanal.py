import os
import json
import sys
import argparse
import unicodedata

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def normalize_str(s):
    """Normaliza texto: mayúsculas, sin espacios laterales y sin acentos."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ''
    s = str(s).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def load_code_maps():
    """Carga código->nombre de provincias y departamentos desde los GeoJSON."""
    prov_map = {}
    prov_path = os.path.join(DATA_DIR, 'provincia.json')
    if os.path.exists(prov_path):
        with open(prov_path, encoding='utf-8') as f:
            for ft in json.load(f).get('features', []):
                p = ft['properties']
                prov_map[str(p['in1']).zfill(2)] = p['nam']

    dept_map = {}
    dept_path = os.path.join(DATA_DIR, 'departamento.json')
    if os.path.exists(dept_path):
        with open(dept_path, encoding='utf-8') as f:
            for ft in json.load(f).get('features', []):
                p = ft['properties']
                dept_map[str(p['in1']).zfill(5)] = p['nam']

    return prov_map, dept_map


def epiweek_to_date(anio, semana):
    """Devuelve la fecha de inicio (domingo) de la semana epidemiológica."""
    from datetime import date, timedelta
    four_jan = date(anio, 1, 4)
    start_se1 = four_jan - timedelta(days=(four_jan.weekday() + 1) % 7)
    return start_se1 + timedelta(weeks=semana - 1)


def build_base_semanal(csv_path):
    """Lee Base_uni.csv y genera data/base_semanal.parquet compatible con el dashboard."""
    prov_map, dept_map = load_code_maps()

    df = pd.read_csv(
        csv_path,
        sep=';',
        encoding='utf-8',
        dtype={'ID_SNVS_EVENTO': str, 'ID_PROVINCIA': str, 'ID_DEPARTAMENTO': str},
        na_values=['', 'NaN', 'NULL'],
    )
    df = df.rename(columns={'CONFIRMADOS': 'CANTIDAD'})

    df['ID_PROVINCIA'] = df['ID_PROVINCIA'].fillna('0')
    df['ID_DEPARTAMENTO'] = df['ID_DEPARTAMENTO'].fillna('0')

    df['CODIGO_PROVINCIA'] = df['ID_PROVINCIA'].astype(str).str.zfill(2)
    df['COD_DEPTO'] = df['ID_DEPARTAMENTO'].astype(str).str.zfill(5)

    df['PROVINCIA'] = df['CODIGO_PROVINCIA'].map(prov_map).fillna('SIN ESPECIFICAR')
    df['DEPARTAMENTO'] = df['COD_DEPTO'].map(dept_map).fillna('SIN ESPECIFICAR')
    df['LOCALIDAD'] = 'SIN ESPECIFICAR'

    df['ANIO'] = (df['ANIO_SEPI_AP'].astype('Int64') // 100).astype('Int64')
    df['SEMANA'] = (df['ANIO_SEPI_AP'].astype('Int64') % 100).astype('Int64')
    df['ANIO'] = df['ANIO'].fillna(0).astype(int)
    df['SEMANA'] = df['SEMANA'].fillna(0).astype(int)

    df['NOMBREEVENTOAGRP'] = df['EVENTO'].map(normalize_str)
    df['ID_SNVS_EVENTO_AGRP'] = (
        df['ID_SNVS_EVENTO']
        .str.extract(r'(\d+)')[0]
        .fillna(0)
        .astype(int)
    )

    df['IDEDAD'] = 0
    df['GRUPO'] = 'SIN ESPECIFICAR'
    df['CANTIDAD'] = df['CANTIDAD'].fillna(0).astype(int)

    # Agregar duplicados por las claves del cuadro agregado
    keys = ['CODIGO_PROVINCIA', 'PROVINCIA', 'COD_DEPTO', 'DEPARTAMENTO', 'LOCALIDAD',
            'ANIO', 'SEMANA', 'NOMBREEVENTOAGRP', 'ID_SNVS_EVENTO_AGRP', 'IDEDAD', 'GRUPO']
    df = df.groupby(keys, as_index=False)['CANTIDAD'].sum()

    # Fecha (inicio de semana epidemiológica) derivada de ANIO/SEMANA
    df['FECHAREGISTROCLINICA'] = df.apply(
        lambda r: epiweek_to_date(int(r['ANIO']), max(int(r['SEMANA']), 1)).isoformat(),
        axis=1,
    )

    # Optimizar tipos de datos
    df['ANIO'] = df['ANIO'].astype('int16')
    df['SEMANA'] = df['SEMANA'].astype('int8')
    df['CANTIDAD'] = df['CANTIDAD'].astype('int32')
    df['ID_SNVS_EVENTO_AGRP'] = df['ID_SNVS_EVENTO_AGRP'].astype('int32')
    df['IDEDAD'] = df['IDEDAD'].astype('int16')

    cols_cat = ['CODIGO_PROVINCIA', 'PROVINCIA', 'COD_DEPTO', 'DEPARTAMENTO',
                'LOCALIDAD', 'NOMBREEVENTOAGRP', 'GRUPO']
    for col in cols_cat:
        df[col] = df[col].astype('category')

    df['FECHAREGISTROCLINICA'] = df['FECHAREGISTROCLINICA'].astype(str)

    col_order = ['CODIGO_PROVINCIA', 'PROVINCIA', 'COD_DEPTO', 'DEPARTAMENTO', 'LOCALIDAD',
                 'ANIO', 'SEMANA', 'NOMBREEVENTOAGRP', 'ID_SNVS_EVENTO_AGRP',
                 'IDEDAD', 'GRUPO', 'CANTIDAD', 'FECHAREGISTROCLINICA']
    df = df[col_order]

    return df


def main():
    parser = argparse.ArgumentParser(description='ETL Base_uni.csv -> base_semanal.parquet')
    parser.add_argument('--csv', default=os.getenv('BASE_UNI_CSV', ''),
                        help='Ruta a Base_uni.csv')
    args = parser.parse_args()

    csv_path = args.csv
    if not csv_path:
        candidates = [
            os.path.join(DATA_DIR, 'Base_uni.csv'),
            os.path.join(DATA_DIR, 'base_uni.csv'),
            r'C:\Users\Casa\Documents\bases\Base_uni.csv',
        ]
        csv_path = next((c for c in candidates if os.path.exists(c)), None)

    if not csv_path or not os.path.exists(csv_path):
        print('Error: no se encontró Base_uni.csv. Usá --csv <ruta> o BASE_UNI_CSV.')
        sys.exit(1)

    print(f'Leyendo {csv_path}...')
    df = build_base_semanal(csv_path)
    print(f'Filas generadas: {len(df)}')

    output_path = os.path.join(DATA_DIR, 'base_semanal.parquet')
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_parquet(output_path, engine='pyarrow', compression='snappy')
    print(f'[OK] base_semanal.parquet actualizado en {output_path}')


if __name__ == '__main__':
    main()
