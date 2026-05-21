"""
ETL Guatemala — extrae:
  - PPOE (precio programado/forecast) del Excel diario del AMM programas_despacho
  - POE  (precio real spot) del ZIP post_despacho POSDESPACHO_DIARIO
  - LBR  (precio nodo 09LBR-230) de CENACE PML MDA
  - Inserta/actualiza en XTS.dbo.GTM (24 filas por dia)

URL PPOE: https://www.amm.org.gt/pdfs2/programas_despacho/
          01_PROGRAMAS_DE_DESPACHO_DIARIO/{año}/
          01_PROGRAMAS_DE_DESPACHO_DIARIO/{MM}_{MES}/WEB{ddmmYYYY}.xlsx
URL POE:  https://www.amm.org.gt/pdfs2/post_despacho/POSDESPACHO_DIARIO/
          {año}/{MM}_{MES}/PD{yyyymmdd}.zip
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import io
import json
import zipfile
import urllib.request
import requests
import pandas as pd
from datetime import date, timedelta, datetime

from etl.common.db_connection import get_connection

# ── Nombres de meses en español (AMM usa mayúsculas) ─────────────────────────
_MESES = {
    "01": "ENERO",   "02": "FEBRERO",  "03": "MARZO",
    "04": "ABRIL",   "05": "MAYO",     "06": "JUNIO",
    "07": "JULIO",   "08": "AGOSTO",   "09": "SEPTIEMBRE",
    "10": "OCTUBRE", "11": "NOVIEMBRE","12": "DICIEMBRE",
}

CENACE_BASE = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"


# ── AMM Excel — POE ───────────────────────────────────────────────────────────
def _amm_url(fecha: date) -> str:
    dd   = fecha.strftime("%d")
    mm   = fecha.strftime("%m")
    yyyy = fecha.strftime("%Y")
    mes  = _MESES[mm]
    ddmmyyyy = fecha.strftime("%d%m%Y")
    return (
        f"https://www.amm.org.gt/pdfs2/programas_despacho/"
        f"01_PROGRAMAS_DE_DESPACHO_DIARIO/{yyyy}/"
        f"01_PROGRAMAS_DE_DESPACHO_DIARIO/{mm}_{mes}/"
        f"WEB{ddmmyyyy}.xlsx"
    )


def get_ppoe(fecha: date) -> pd.Series:
    """
    Descarga el Excel de programas_despacho y extrae las 24 horas del PPOE (forecast).
    Retorna una Series de 24 valores float (USD/MWh) o None si no hay datos.
    """
    url = _amm_url(fecha)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        df = pd.read_excel(io.BytesIO(data), sheet_name="POE", skiprows=8, header=None)
        ppoe = pd.to_numeric(df.iloc[0:24, 4], errors="coerce")
        ppoe.index = range(24)
        return ppoe
    except Exception as e:
        print(f"[GTM] PPOE no disponible para {fecha}: {e}")
        return pd.Series([None] * 24)


# Alias de compatibilidad para código existente
get_poe = get_ppoe


def _posdespacho_url(fecha: date) -> str:
    yyyy = fecha.strftime("%Y")
    mm   = fecha.strftime("%m")
    mes  = _MESES[mm]
    yyyymmdd = fecha.strftime("%Y%m%d")
    return (
        f"https://www.amm.org.gt/pdfs2/post_despacho/POSDESPACHO_DIARIO/{yyyy}/"
        f"{mm}_{mes}/PD{yyyymmdd}.zip"
    )


def get_poe_real(fecha: date) -> pd.Series:
    """
    Descarga el ZIP de post_despacho y extrae las 24 horas del POE real (spot).
    Retorna una Series de 24 valores float (USD/MWh) o None si no hay datos.
    El archivo suele estar disponible al dia siguiente del despacho.
    """
    url = _posdespacho_url(fecha)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        z = zipfile.ZipFile(io.BytesIO(data))
        xl_name = next((n for n in z.namelist() if n.lower().endswith(".xlsx")), None)
        if not xl_name:
            raise ValueError("No xlsx in ZIP")
        df = pd.read_excel(io.BytesIO(z.read(xl_name)), sheet_name="POE",
                           skiprows=5, header=None)
        # Fila 0 = encabezado, filas 1-24 = horas 0-23
        poe = pd.to_numeric(df.iloc[1:25, 5], errors="coerce")
        poe.index = range(24)
        return poe
    except Exception as e:
        print(f"[GTM] POE real no disponible para {fecha}: {e}")
        return pd.Series([None] * 24)


# ── CENACE — PML nodo 09LBR-230 ──────────────────────────────────────────────
def get_lbr(fecha: date) -> pd.Series:
    """
    Consulta el PML MDA de CENACE para el nodo 09LBR-230 (SIN).
    Retorna una Series de 24 valores float o NaN si no hay datos.
    """
    dd   = fecha.strftime("%d")
    mm   = fecha.strftime("%m")
    yyyy = fecha.strftime("%Y")
    url = f"{CENACE_BASE}/SIN/MDA/09LBR-230/{yyyy}/{mm}/{dd}/{yyyy}/{mm}/{dd}/JSON"
    try:
        resp = requests.get(url, timeout=30, verify=False)
        res_dict = json.loads(resp.content)
        valores = res_dict["Resultados"][0]["Valores"]
        lbr = pd.Series([float(v["pml"]) for v in valores])
        lbr.index = range(len(lbr))
        return lbr.reindex(range(24))
    except Exception as e:
        print(f"[GTM] LBR CENACE no disponible para {fecha}: {e}")
        return pd.Series([None] * 24)


# ── Extracción principal ──────────────────────────────────────────────────────
def extract_gtm(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae PPOE, POE real y LBR para cada dia en [fecha_ini, fecha_fin].
    Retorna DataFrame con columnas: fecha (datetime, hora por hora), PPOE, POE, LBR.
    """
    rows = []
    for fecha in pd.date_range(fecha_ini, fecha_fin, freq="D"):
        d = fecha.date()
        print(f"[GTM] {d}")
        ppoe_series = get_ppoe(d)
        poe_series  = get_poe_real(d)
        lbr_series  = get_lbr(d)
        for hora in range(24):
            ts = datetime.combine(d, datetime.min.time()) + timedelta(hours=hora)
            rows.append({
                "fecha": ts,
                "PPOE":  ppoe_series[hora] if hora < len(ppoe_series) else None,
                "POE":   poe_series[hora]  if hora < len(poe_series)  else None,
                "LBR":   lbr_series[hora]  if hora < len(lbr_series)  else None,
            })
    return pd.DataFrame(rows)


# ── Upsert en SQL Server ──────────────────────────────────────────────────────
def upsert_gtm(df: pd.DataFrame) -> None:
    """Inserta o actualiza filas en XTS.dbo.GTM."""
    if df.empty:
        print("[GTM] Sin datos.")
        return

    conn   = get_connection("XTS")
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute("SELECT COUNT(*) FROM GTM WHERE fecha = ?", row["fecha"])
        existe = cursor.fetchone()[0]

        ppoe = row["PPOE"] if pd.notna(row.get("PPOE")) else None
        poe  = row["POE"]  if pd.notna(row.get("POE"))  else None
        lbr  = row["LBR"]  if pd.notna(row.get("LBR"))  else None

        if existe:
            cursor.execute(
                "UPDATE GTM SET PPOE = ?, POE = ?, LBR = ? WHERE fecha = ?",
                ppoe, poe, lbr, row["fecha"]
            )
        else:
            cursor.execute(
                "INSERT INTO GTM (fecha, PPOE, POE, LBR) VALUES (?, ?, ?, ?)",
                row["fecha"], ppoe, poe, lbr
            )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[GTM] {len(df)} filas guardadas.")
