"""
ETL CENACE - Extractor de precios PML (MDA y MTR)
Basado en api_stuff.py (Marco, Feb 2026)

API publica CENACE SW-PML:
  https://ws01.cenace.gob.mx:8082/SWPML/SIM/{sistema}/{proceso}/{nodos}/
  {anio_ini}/{mes_ini}/{dia_ini}/{anio_fin}/{mes_fin}/{dia_fin}/JSON

Limites de la API:
  - Max 7 dias por request
  - Max 20 nodos por request
"""

import requests
import time
import logging
from datetime import date, datetime, timedelta
from itertools import islice

import pandas as pd

from etl.common.db_connection import get_connection
from etl.cenace.nodes_list import ZONAS

logger = logging.getLogger(__name__)

BASE_URL = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"
MAX_DIAS = 7
MAX_NODOS = 20
SLEEP_ENTRE_REQUESTS = 0.5  # segundos entre llamadas a la API


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _batches(iterable, size):
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield batch


def _date_ranges(fecha_ini, fecha_fin, max_dias=MAX_DIAS):
    """Divide un rango en ventanas de max_dias dias."""
    current = fecha_ini
    while current <= fecha_fin:
        end = min(current + timedelta(days=max_dias - 1), fecha_fin)
        yield current, end
        current = end + timedelta(days=1)


def _fetch(sistema, proceso, nodos, fecha_ini, fecha_fin):
    """
    Llama a la API de CENACE para un batch de nodos y un rango <= 7 dias.
    Retorna lista de dicts con los valores, o [] si no hay datos.
    """
    lista_nodos = ",".join(nodos)
    url = (
        f"{BASE_URL}/{sistema}/{proceso}/{lista_nodos}/"
        f"{fecha_ini.year}/{fecha_ini.month:02d}/{fecha_ini.day:02d}/"
        f"{fecha_fin.year}/{fecha_fin.month:02d}/{fecha_fin.day:02d}/JSON"
    )

    try:
        r = requests.get(url, timeout=30, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"Error en request: {url} -> {e}")
        return []

    if data.get("status") == "ZERO_RESULTS":
        return []

    rows = []
    for resultado in data.get("Resultados", []):
        nodo = resultado.get("clv_nodo", "")
        for v in resultado.get("Valores", []):
            v["clv_nodo"] = nodo
            v["sistema"] = sistema
            rows.append(v)

    return rows


# ---------------------------------------------------------------------------
# Extraccion MDA -> tabla PML.MDA_D
# ---------------------------------------------------------------------------

def extract_mda(fecha_ini: date, fecha_fin: date) -> pd.DataFrame:
    """
    Extrae precios MDA de CENACE para las 108 zonas en el rango dado.
    Retorna DataFrame con columnas: fecha, Sistema, Zona_Carga, PZ, PZ_ENE, PZ_PER, PZ_CNG
    """
    all_rows = []

    for sistema, zonas_sistema in _group_by_sistema():
        for batch_nodos in _batches(zonas_sistema, MAX_NODOS):
            for f_ini, f_fin in _date_ranges(fecha_ini, fecha_fin):
                rows = _fetch(sistema, "MDA", batch_nodos, f_ini, f_fin)
                all_rows.extend(rows)
                time.sleep(SLEEP_ENTRE_REQUESTS)

    if not all_rows:
        logger.warning(f"MDA: sin datos para {fecha_ini} - {fecha_fin}")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df.rename(columns={
        "clv_nodo": "Zona_Carga",
        "sistema": "Sistema",
        "hora": "hora",
        "pz": "PZ",
        "pz_ene": "PZ_ENE",
        "pz_per": "PZ_PER",
        "pz_cng": "PZ_CNG",
    })

    # Construir columna fecha como datetime con hora
    df["hora"] = pd.to_numeric(df["hora"], errors="coerce").astype(int)
    df["fecha_base"] = df.apply(
        lambda r: r.get("fecha", None), axis=1
    )
    # La API devuelve fecha en cada valor o se puede inferir del rango
    # Construimos la fecha completa: fecha + hora (hora 1 = 01:00)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"]) + pd.to_timedelta(df["hora"] - 1, unit="h")
    else:
        # Fallback: no tenemos fecha en el valor, se infiere del contexto
        logger.warning("Campo 'fecha' no encontrado en respuesta de API")
        return pd.DataFrame()

    return df[["fecha", "Sistema", "Zona_Carga", "PZ", "PZ_ENE", "PZ_PER", "PZ_CNG"]].dropna()


def extract_mtr(fecha_ini: date, fecha_fin: date) -> pd.DataFrame:
    """
    Extrae precios MTR de CENACE para las 108 zonas en el rango dado.
    Retorna DataFrame con columnas: fecha, Sistema, Nodo, PML, PML_ENE, PML_PER, PML_CNG
    """
    all_rows = []

    for sistema, zonas_sistema in _group_by_sistema():
        for batch_nodos in _batches(zonas_sistema, MAX_NODOS):
            for f_ini, f_fin in _date_ranges(fecha_ini, fecha_fin):
                rows = _fetch(sistema, "MTR", batch_nodos, f_ini, f_fin)
                all_rows.extend(rows)
                time.sleep(SLEEP_ENTRE_REQUESTS)

    if not all_rows:
        logger.warning(f"MTR: sin datos para {fecha_ini} - {fecha_fin}")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df.rename(columns={
        "clv_nodo": "Nodo",
        "sistema": "Sistema",
        "hora": "hora",
        "pml": "PML",
        "pml_ene": "PML_ENE",
        "pml_per": "PML_PER",
        "pml_cng": "PML_CNG",
    })

    df["hora"] = pd.to_numeric(df["hora"], errors="coerce").astype(int)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"]) + pd.to_timedelta(df["hora"] - 1, unit="h")
    else:
        logger.warning("Campo 'fecha' no encontrado en respuesta MTR")
        return pd.DataFrame()

    return df[["fecha", "Sistema", "Nodo", "PML", "PML_ENE", "PML_PER", "PML_CNG"]].dropna()


# ---------------------------------------------------------------------------
# Insercion en BD
# ---------------------------------------------------------------------------

def upsert_mda(df: pd.DataFrame):
    """Inserta filas de MDA_D que no existen ya (por fecha + Sistema + Zona_Carga)."""
    if df.empty:
        return 0

    conn = get_connection("PML")
    cursor = conn.cursor()

    sql = """
        IF NOT EXISTS (
            SELECT 1 FROM MDA_D
            WHERE fecha = ? AND CAST(Sistema AS VARCHAR) = ? AND CAST(Zona_Carga AS VARCHAR) = ?
        )
        INSERT INTO MDA_D (fecha, Sistema, Zona_Carga, PZ, PZ_ENE, PZ_PER, PZ_CNG)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    inserted = 0
    for _, row in df.iterrows():
        cursor.execute(sql, (
            row["fecha"], row["Sistema"], row["Zona_Carga"],
            row["fecha"], row["Sistema"], row["Zona_Carga"],
            row["PZ"], row["PZ_ENE"], row["PZ_PER"], row["PZ_CNG"],
        ))
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()
    logger.info(f"MDA_D: {inserted} filas insertadas de {len(df)}")
    return inserted


def upsert_mtr(df: pd.DataFrame):
    """Inserta filas de MTR que no existen ya (por fecha + Sistema + Nodo)."""
    if df.empty:
        return 0

    conn = get_connection("PML")
    cursor = conn.cursor()

    sql = """
        IF NOT EXISTS (
            SELECT 1 FROM MTR
            WHERE fecha = ? AND CAST(Sistema AS VARCHAR) = ? AND CAST(Nodo AS VARCHAR) = ?
        )
        INSERT INTO MTR (fecha, Sistema, Nodo, PML, PML_ENE, PML_PER, PML_CNG)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    inserted = 0
    for _, row in df.iterrows():
        cursor.execute(sql, (
            row["fecha"], row["Sistema"], row["Nodo"],
            row["fecha"], row["Sistema"], row["Nodo"],
            row["PML"], row["PML_ENE"], row["PML_PER"], row["PML_CNG"],
        ))
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()
    logger.info(f"MTR: {inserted} filas insertadas de {len(df)}")
    return inserted


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _group_by_sistema():
    """Agrupa ZONAS por sistema."""
    sistemas = {}
    for zona, sistema in ZONAS:
        sistemas.setdefault(sistema, []).append(zona)
    return sistemas.items()
