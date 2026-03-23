"""
ETL Temperaturas — extrae temperatura horaria para 10 ciudades via Open-Meteo.

Open-Meteo es gratuita, sin API key y tiene datos históricos desde 1940.
  - Histórico : https://archive-api.open-meteo.com/v1/archive
  - Forecast  : https://api.open-meteo.com/v1/forecast

Ciudades:
  TIJ = Tijuana, MXL = Mexicali, SND = San Diego, IVY = Imperial (El Centro)
  NLR = Nuevo Laredo, LRD = Laredo TX, RYN = Reynosa, MCA = McAllen
  TPC = Tampico, GTM = Ciudad de Guatemala

Tabla destino: XTS.dbo.TEMPERATURAS
  Columnas: fecha (datetime, hora por hora), TIJ, MXL, SND, IVY,
            NLR, LRD, RYN, MCA, TPC, GTM  (todas FLOAT, °C)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
import pandas as pd
from datetime import date, timedelta, datetime

from etl.common.db_connection import get_connection

# ── Coordenadas de cada ciudad ────────────────────────────────────────────────
CIUDADES = {
    "TIJ": ( 32.5149, -117.0382),  # Tijuana
    "MXL": ( 32.6245, -115.4523),  # Mexicali
    "SND": ( 32.7157, -117.1611),  # San Diego
    "IVY": ( 32.7920, -115.5629),  # Imperial Valley / El Centro
    "NLR": ( 27.4760,  -99.5164),  # Nuevo Laredo
    "LRD": ( 27.5306,  -99.4803),  # Laredo TX
    "RYN": ( 26.0844,  -98.2943),  # Reynosa
    "MCA": ( 26.2034,  -98.2301),  # McAllen
    "TPC": ( 22.2475,  -97.8661),  # Tampico
    "GTM": ( 14.6349,  -90.5069),  # Ciudad de Guatemala
}

ARCHIVE_URL  = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _get_temps(ciudad: str, lat: float, lon: float,
               fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Descarga temperatura horaria para una ciudad.
    Usa archive API para fechas pasadas y forecast para fechas futuras.
    Retorna DataFrame con columnas: fecha, {ciudad}.
    """
    hoy = date.today()
    ayer = hoy - timedelta(days=2)   # archive tiene ~2 días de retraso

    ini = pd.Timestamp(fecha_ini).date()
    fin = pd.Timestamp(fecha_fin).date()

    dfs = []

    # ── Datos históricos ──────────────────────────────────────────────────────
    if ini <= ayer:
        hist_fin = min(fin, ayer).strftime("%Y-%m-%d")
        params = {
            "latitude":   lat,
            "longitude":  lon,
            "start_date": fecha_ini,
            "end_date":   hist_fin,
            "hourly":     "temperature_2m",
            "timezone":   "America/Mexico_City",
        }
        resp = requests.get(ARCHIVE_URL, params=params, timeout=30)
        resp.raise_for_status()
        js = resp.json()
        df_h = pd.DataFrame({
            "fecha": pd.to_datetime(js["hourly"]["time"]),
            ciudad:  js["hourly"]["temperature_2m"],
        })
        dfs.append(df_h)

    # ── Pronóstico (hoy en adelante) ──────────────────────────────────────────
    if fin > ayer:
        params = {
            "latitude":      lat,
            "longitude":     lon,
            "hourly":        "temperature_2m",
            "timezone":      "America/Mexico_City",
            "forecast_days": min((fin - hoy).days + 2, 16),
        }
        resp = requests.get(FORECAST_URL, params=params, timeout=30)
        resp.raise_for_status()
        js = resp.json()
        df_f = pd.DataFrame({
            "fecha": pd.to_datetime(js["hourly"]["time"]),
            ciudad:  js["hourly"]["temperature_2m"],
        })
        # Filtrar solo el rango solicitado
        fcst_ini = max(ini, ayer + timedelta(days=1))
        df_f = df_f[df_f["fecha"].dt.date >= fcst_ini]
        df_f = df_f[df_f["fecha"].dt.date <= fin]
        dfs.append(df_f)

    if not dfs:
        return pd.DataFrame(columns=["fecha", ciudad])

    return pd.concat(dfs).drop_duplicates("fecha").sort_values("fecha").reset_index(drop=True)


# ── Extracción de todas las ciudades ─────────────────────────────────────────
def extract_temperaturas(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae temperatura horaria para todas las ciudades en el rango.
    Retorna DataFrame con columnas: fecha, TIJ, MXL, SND, IVY, NLR, LRD, RYN, MCA, TPC, GTM.
    """
    fechas = pd.date_range(fecha_ini, fecha_fin + " 23:00", freq="h")
    df = pd.DataFrame({"fecha": fechas})

    for ciudad, (lat, lon) in CIUDADES.items():
        print(f"[TEMP] {ciudad}...")
        try:
            df_c = _get_temps(ciudad, lat, lon, fecha_ini, fecha_fin)
            df = df.merge(df_c, on="fecha", how="left")
        except Exception as e:
            print(f"[TEMP] {ciudad} falló: {e}")
            df[ciudad] = None

    return df


# ── Upsert ────────────────────────────────────────────────────────────────────
def upsert_temperaturas(df: pd.DataFrame) -> None:
    """Inserta o actualiza en XTS.dbo.TEMPERATURAS."""
    if df.empty:
        print("[TEMP] Sin datos.")
        return

    ciudades = list(CIUDADES.keys())
    conn   = get_connection("XTS")
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM TEMPERATURAS WHERE fecha = ?", row["fecha"])
        existe = cursor.fetchone()[0]

        vals = {c: (float(row[c]) if c in row and pd.notna(row[c]) else None)
                for c in ciudades}

        if existe:
            sets = ", ".join(f"{c} = ?" for c in ciudades)
            cursor.execute(
                f"UPDATE TEMPERATURAS SET {sets} WHERE fecha = ?",
                *vals.values(), row["fecha"]
            )
        else:
            cols = ["fecha"] + ciudades
            placeholders = ", ".join("?" * len(cols))
            cursor.execute(
                f"INSERT INTO TEMPERATURAS ({', '.join(cols)}) VALUES ({placeholders})",
                row["fecha"], *vals.values()
            )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[TEMP] {len(df)} filas guardadas en TEMPERATURAS.")


# ── CLI rápido ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ETL Temperaturas — Open-Meteo")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--desde",   type=str)
    parser.add_argument("--hasta",   type=str)
    args = parser.parse_args()

    if args.backfill and args.desde and args.hasta:
        fi, ff = args.desde, args.hasta
    else:
        ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        manana = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        fi, ff = ayer, manana

    df = extract_temperaturas(fi, ff)
    print(df.head(10).to_string(index=False))
    upsert_temperaturas(df)
