# utils/query_builder.py
import re
import unicodedata
import pandas as pd
from typing import Dict, Tuple
import streamlit as st
from utils.common import get_distinct_departments, get_distinct_provinces

class NaturalLanguageQueryBuilder:
    """
    Sistema basado en reglas para convertir consultas en lenguaje natural a SQL.
    Usa valores nacionales extraídos del parquet y alias de departamentos y provincias.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        text = unicodedata.normalize('NFKD', str(text))
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower()
        return re.sub(r'\s+', ' ', text).strip()

    def __init__(self):
        # Cargar valores nacionales a partir del parquet
        self.provincias_validas = [p for p in get_distinct_provinces() if isinstance(p, str)]
        self.departamentos_validos = [d for d in get_distinct_departments() if isinstance(d, str)]

        self.provincias_aliases = {self.normalize_text(p): p for p in self.provincias_validas}
        self.departamentos_aliases = {self.normalize_text(d): d for d in self.departamentos_validos}

        # Alias adicionales para nombres naturales y abreviaturas comunes
        adicional_aliases = {
            'caba': 'CABA',
            'ciudad autonoma de buenos aires': 'CABA',
            'capital federal': 'CABA',
            'buenos aires ciudad': 'CABA',
            'mar del plata': 'General Pueyrredón',
            'mdp': 'General Pueyrredón',
        }
        for alias, destino in adicional_aliases.items():
            self.departamentos_aliases[self.normalize_text(alias)] = destino

        # Sinónimos adicionales de departamentos comunes
        self.departamentos_aliases.update({
            '25 de mayo': '25 de Mayo', 'veinticinco de mayo': '25 de Mayo',
            '9 de julio': '9 de Julio', 'nueve de julio': '9 de Julio',
            'adolfo gonzales chaves': 'Adolfo Gonzales Chaves', 'gonzales chaves': 'Adolfo Gonzales Chaves', 'chaves': 'Adolfo Gonzales Chaves',
            'almirante brown': 'Almirante Brown', 'brown': 'Almirante Brown',
            'bahia blanca': 'Bahía Blanca', 'b blanca': 'Bahía Blanca',
            'benito juarez': 'Benito Juárez',
            'capitan sarmiento': 'Capitán Sarmiento',
            'carmen de areco': 'Carmen de Areco',
            'coronel de marina l rosales': 'Coronel de Marina L. Rosales', 'coronel rosales': 'Coronel de Marina L. Rosales', 'rosales': 'Coronel de Marina L. Rosales',
            'coronel dorrego': 'Coronel Dorrego', 'dorrego': 'Coronel Dorrego',
            'coronel pringles': 'Coronel Pringles', 'pringles': 'Coronel Pringles',
            'coronel suarez': 'Coronel Suárez', 'suarez': 'Coronel Suárez',
            'esteban echeverria': 'Esteban Echeverría', 'echeverria': 'Esteban Echeverría',
            'exaltacion de la cruz': 'Exaltación de la Cruz',
            'florencio varela': 'Florencio Varela', 'varela': 'Florencio Varela',
            'florentino ameghino': 'Florentino Ameghino', 'ameghino': 'Florentino Ameghino',
            'hipolito yrigoyen': 'Hipólito Yrigoyen', 'yrigoyen': 'Hipólito Yrigoyen',
            'ituzaingo': 'Ituzaingó',
            'jose c paz': 'José C. Paz', 'j.c. paz': 'José C. Paz',
            'leandro n alem': 'Leandro N. Alem', 'alem': 'Leandro N. Alem',
            'lomas': 'Lomas de Zamora',
            'malvinas': 'Malvinas Argentinas',
            'marcos paz': 'Marcos Paz',
            'monte hermoso': 'Monte Hermoso',
            'pehuajo': 'Pehuajó',
            'presidente peron': 'Presidente Perón', 'p peron': 'Presidente Perón',
            'punta indio': 'Punta Indio',
            'san andres de giles': 'San Andrés de Giles', 'giles': 'San Andrés de Giles',
            'san antonio de areco': 'San Antonio de Areco',
            'san fernando': 'San Fernando',
            'san isidro': 'San Isidro',
            'san miguel': 'San Miguel',
            'san nicolas': 'San Nicolás',
            'san vicente': 'San Vicente',
            'tres arroyos': 'Tres Arroyos',
            'tres de febrero': 'Tres de Febrero',
            'tres lomas': 'Tres Lomas',
            'vicente lopez': 'Vicente López',
            'general alvarado': 'General Alvarado', 'gral alvarado': 'General Alvarado',
            'general arenales': 'General Arenales', 'gral arenales': 'General Arenales',
            'general belgrano': 'General Belgrano', 'gral belgrano': 'General Belgrano',
            'general guido': 'General Guido', 'gral guido': 'General Guido',
            'general juan madariaga': 'General Juan Madariaga', 'gral madariaga': 'General Juan Madariaga',
            'general la madrid': 'General La Madrid', 'gral la madrid': 'General La Madrid',
            'general las heras': 'General Las Heras', 'gral las heras': 'General Las Heras',
            'general lavalle': 'General Lavalle', 'gral lavalle': 'General Lavalle',
            'general paz': 'General Paz', 'gral paz': 'General Paz',
            'general pinto': 'General Pinto', 'gral pinto': 'General Pinto',
            'general pueyrredon': 'General Pueyrredón', 'mdp': 'General Pueyrredón',
            'general rodriguez': 'General Rodríguez',
            'general san martin': 'General San Martín', 'gral san martin': 'General San Martín',
            'general viamonte': 'General Viamonte', 'general villegas': 'General Villegas',
        })

        # Regiones agregadas para consultas nacionales
        self.gba = {
            'gba': ['Avellaneda', 'Quilmes', 'Berazategui', 'Florencio Varela', 'Almirante Brown',
                    'Tres de Febrero', 'Hurlingham', 'Ituzaingó', 'Morón', 'Castelar', 'San Martín',
                    'Merlo', 'Moreno', 'General Sarmiento', 'Presidente Perón', 'Lomas de Zamora',
                    'Lanús', 'Pilar', 'Escobar', 'La Matanza'],
            'conurbano': ['Avellaneda', 'Quilmes', 'Berazategui', 'Florencio Varela', 'Almirante Brown',
                          'Tres de Febrero', 'Hurlingham', 'Ituzaingó', 'Morón', 'Castelar', 'San Martín',
                          'Merlo', 'Moreno', 'General Sarmiento', 'Presidente Perón', 'Lomas de Zamora',
                          'Lanús', 'Pilar', 'Escobar', 'La Matanza'],
        }

        self.eventos_keywords = {
            'bronquiolitis': 'BRONQUIOLITIS',
            'bronquilitis': 'BRONQUIOLITIS',
            'bronquioliti': 'BRONQUIOLITIS',
            'bronquiliti': 'BRONQUIOLITIS',
            'bronco': 'BRONQUIOLITIS',
            'diarrea': 'DIARREA',
            'diarreas': 'DIARREA',
            'influenza': 'INFLUENZA',
            'gripe': 'INFLUENZA',
            'eti': 'ETI',
            'irag': 'IRAG',
            'infeccion respiratoria': 'IRAG',
            'respiratoria aguda': 'IRAG',
            'neumonia': 'NEUMONIA',
            'neumonía': 'NEUMONIA',
            'pulmonia': 'NEUMONIA',
            'dengue': 'DENGUE',
            'covid': 'COVID',
            'coronavirus': 'COVID',
            'sarampion': 'SARAMPION',
            'varicela': 'VARICELA',
        }

    def parse_query(self, query_text: str) -> Dict:
        """
        Analiza la consulta en lenguaje natural y extrae parámetros.

        Returns:
            Dict con keys: departamentos, provincias, eventos, años, accion
        """
        text_norm = self.normalize_text(query_text)
        result = {
            'provincias': [],
            'departamentos': [],
            'eventos': [],
            'años': [],
            'accion': 'tabla',
            'success': True,
            'message': ''
        }

        # Detectar departamentos
        for keyword, departamento in self.departamentos_aliases.items():
            if keyword in text_norm and departamento not in result['departamentos']:
                result['departamentos'].append(departamento)

        # Detectar provincias
        for keyword, provincia in self.provincias_aliases.items():
            if keyword in text_norm and provincia not in result['provincias']:
                result['provincias'].append(provincia)

        # Detectar regiones especiales (GBA, conurbano)
        for region, departamentos in self.gba.items():
            if region in text_norm:
                for departamento in departamentos:
                    if departamento not in result['departamentos']:
                        result['departamentos'].append(departamento)

        # Detectar eventos
        for keyword, evento in self.eventos_keywords.items():
            if keyword in text_norm and evento not in result['eventos']:
                result['eventos'].append(evento)

        # Detectar años
        años_match = re.findall(r'\b(20[0-4][0-9])\b', query_text)
        if años_match:
            result['años'] = sorted([int(año) for año in set(años_match)])

        rango_match = re.search(r'(?:entre|desde)\s+(\d{4})\s+(?:y|hasta|a)\s+(\d{4})', text_norm)
        if rango_match:
            año_inicio = int(rango_match.group(1))
            año_fin = int(rango_match.group(2))
            result['años'] = list(range(año_inicio, año_fin + 1))

        if any(word in text_norm for word in ['grafico', 'gráfico', 'graficá', 'graficar', 'visualizar', 'mostrar grafico']):
            result['accion'] = 'grafico'
        elif any(word in text_norm for word in ['total', 'suma', 'cantidad total', 'cuanto', 'cuánto']):
            result['accion'] = 'total'

        if not result['provincias'] and not result['departamentos'] and not result['eventos'] and not result['años']:
            result['success'] = False
            result['message'] = '⚠️ No pude detectar provincias, departamentos, eventos o años en tu consulta. Intenta ser más específico.'

        if result['provincias'] and result['departamentos']:
            # Si hay provincia y departamentos, priorizamos provincia
            result['departamentos'] = []

        return result

    def build_duckdb_query(self, params: Dict, parquet_path: str) -> str:
        """
        Construye una consulta DuckDB basada en los parámetros extraídos.
        """
        is_province_level = bool(params.get('provincias')) and not bool(params.get('departamentos'))

        select_cols = "PROVINCIA,\n            DEPARTAMENTO" if not is_province_level else "PROVINCIA"
        group_cols = "PROVINCIA, DEPARTAMENTO, ANIO, SEMANA, NOMBREEVENTOAGRP" if not is_province_level else "PROVINCIA, ANIO, SEMANA, NOMBREEVENTOAGRP"
        order_cols = "PROVINCIA, ANIO, SEMANA" if is_province_level else "PROVINCIA, DEPARTAMENTO, ANIO, SEMANA"

        query = f"""
        SELECT
            {select_cols},
            ANIO,
            SEMANA,
            NOMBREEVENTOAGRP,
            SUM(CANTIDAD) AS CANTIDAD
        FROM '{parquet_path}'
        WHERE 1=1
        """

        if params.get('departamentos'):
            departamentos_str = "', '".join([dep.upper() for dep in params['departamentos']])
            query += f"\n    AND UPPER(DEPARTAMENTO) IN ('{departamentos_str}')"
        if params.get('provincias'):
            provincias_str = "', '".join([prov.upper() for prov in params['provincias']])
            query += f"\n    AND UPPER(PROVINCIA) IN ('{provincias_str}')"

        if params.get('eventos'):
            eventos_conditions = [f"UPPER(NOMBREEVENTOAGRP) LIKE UPPER('%{evento}%')" for evento in params['eventos']]
            query += f"\n    AND ({' OR '.join(eventos_conditions)})"

        if params.get('años'):
            años_str = ', '.join(map(str, params['años']))
            query += f"\n    AND ANIO IN ({años_str})"

        query += f"""
        GROUP BY {group_cols}
        ORDER BY {order_cols}
        """
        return query

    def execute_query(self, query_text: str, parquet_path: str) -> Tuple[pd.DataFrame, Dict]:
        import duckdb

        params = self.parse_query(query_text)
        if not params['success']:
            return pd.DataFrame(), params

        try:
            sql_query = self.build_duckdb_query(params, parquet_path)
            with duckdb.connect() as con:
                df = con.execute(sql_query).df()

            params['sql_query'] = sql_query
            params['message'] = f"✅ Encontrados {len(df)} registros"
            return df, params
        except Exception as e:
            params['success'] = False
            params['message'] = f'❌ Error al ejecutar consulta: {str(e)}'
            return pd.DataFrame(), params

    def get_available_values(self, parquet_path: str) -> Dict:
        import duckdb
        try:
            with duckdb.connect() as con:
                eventos = con.execute(f"SELECT DISTINCT NOMBREEVENTOAGRP FROM '{parquet_path}' ORDER BY NOMBREEVENTOAGRP").df()
                años = con.execute(f"SELECT DISTINCT ANIO FROM '{parquet_path}' ORDER BY ANIO DESC").df()
                provincias = con.execute(f"SELECT DISTINCT PROVINCIA FROM '{parquet_path}' ORDER BY PROVINCIA").df()
                return {
                    'eventos': eventos['NOMBREEVENTOAGRP'].tolist(),
                    'años': años['ANIO'].tolist(),
                    'provincias': provincias['PROVINCIA'].tolist()
                }
        except Exception as e:
            st.error(f"Error al obtener valores: {e}")
            return {'eventos': [], 'años': [], 'provincias': []}
