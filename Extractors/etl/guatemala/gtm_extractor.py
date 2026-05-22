"""
ETL Guatemala — extrae:
  - PPOE (precio programado/forecast) del Excel diario del AMM (programas_despacho)
  - POE  (precio real/spot) del ZIP post_despacho del AMM
  - LBR  (precio nodo 09LBR-230) de CENACE PML MDA
  - Inserta/actualiza en XTS.dbo.GTM (24 filas por dia)

PPOE URL: amm.org.gt/pdfs2/programas_despacho/01_PROGRAMAS_DE_DESPACHO_DIARIO/{año}/...WEB{ddmmYYYY}.xlsx
POE  URL: amm.org.gt/pdfs2/post_despacho/POSDESPACHO_DIARIO/{yyyy}/{mm}_{MES}/PD{yyyymmdd}.zip
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import io
import json
import math
import zipfile
import urllib.request
import requests
import pandas as pd
from datetime import date, timedelta, datetime

from etl.base.db import get_connection

# ── Nombres de meses en español (AMM usa mayúsculas) ─────────────────────────
_MESES = {
    "01": "ENERO",   "02": "FEBRERO",  "03": "MARZO",
    "04": "ABRIL",   "05": "MAYO",     "06": "JUNIO",
    "07": "JULIO",   "08": "AGOSTO",   "09": "SEPTIEMBRE",
    "10": "OCTUBRE", "11": "NOVIEMBRE","12": "DICIEMBRE",
}

CENACE_BASE = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"


def _safe(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ── AMM URLs ──────────────────────────────────────────────────────────────────
def _amm_ppoe_url(fecha: date) -> str:
    """URL del Excel de programa de despacho diario (PPOE forecast)."""
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


def _posdespacho_url(fecha: date) -> str:
    """URL del ZIP de post-despacho diario (POE precio real)."""
    yyyy     = fecha.strftime("%Y")
    mm       = fecha.strftime("%m")
    mes      = _MESES[mm]
    yyyymmdd = fecha.strftime("%Y%m%d")
    return (
        f"https://www.amm.org.gt/pdfs2/post_despacho/"
        f"POSDESPACHO_DIARIO/{yyyy}/{mm}_{mes}/PD{yyyymmdd}.zip"
    )


# ── PPOE (programa de despacho — forecast) ────────────────────────────────────
def get_ppoe(fecha: date) -> pd.Series:
    """
    Descarga el Excel del AMM y extrae las 24 horas del PPOE.
    Sheet "POE", skiprows=8, col 4 (0-indexed), rows 0-23.
    Retorna Series de 24 valores float o None.
    """
    url = _amm_ppoe_url(fecha)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        df = pd.read_excel(io.BytesIO(data), sheet_name="POE", skiprows=8, header=None)
        series = pd.to_numeric(df.iloc[0:24, 4], errors="coerce")
        series.index = range(24)
        return series
    except Exception as e:
        print(f"[GTM] PPOE no disponible para {fecha}: {e}")
        return pd.Series([None] * 24)

# Alias para backward compat
get_poe = get_ppoe


# ── POE real (post-despacho) ──────────────────────────────────────────────────
def get_poe_real(fecha: date) -> pd.Series:
    """
    Descarga el ZIP del post-despacho AMM y extrae las 24 horas del precio real POE.
    ZIP contiene "{dd} {mes} {yyyy}.xlsx", sheet "POE", skiprows=5, col 5, rows 1-24.
    Retorna Series de 24 valores float o None.
    """
    url = _posdespacho_url(fecha)
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            fname = zf.namelist()[0]
            with zf.open(fname) as f:
                xl_data = f.read()

        df = pd.read_excel(io.BytesIO(xl_data), sheet_name="POE", skiprows=5, header=None)
        series = pd.to_numeric(df.iloc[1:25, 5], errors="coerce")
        series.index = range(24)
        return series
    except Exception as e:
        print(f"[GTM] POE real no disponible para {fecha}: {e}")
        return pd.Series([None] * 24)


# ── CENACE — PML nodo 09LBR-230 ──────────────────────────────────────────────
def get_lbr(fecha: date) -> pd.Series:
    """
    Consulta el PML MDA de CENACE para el nodo 09LBR-230 (SIN).
    Retorna Series de 24 valores float o None.
    """
    mm   = fecha.strftime("%m")
    yyyy = fecha.strftime("%Y")
    dd   = fecha.strftime("%d")
    url  = f"{CENACE_BASE}/SIN/MDA/09LBR-230/{yyyy}/{mm}/{dd}/{yyyy}/{mm}/{dd}/JSON"
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
    Retorna DataFrame: fecha (datetime horario), PPOE, POE, LBR.
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
                "PPOE":  _safe(ppoe_series[hora] if hora < len(ppoe_series) else None),
                "POE":   _safe(poe_series[hora]  if hora < len(poe_series)  else None),
                "LBR":   _safe(lbr_series[hora]  if hora < len(lbr_series)  else None),
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

        ppoe = _safe(row.get("PPOE"))
        poe  = _safe(row.get("POE"))
        lbr  = _safe(row.get("LBR"))

        if existe:
            cursor.execute(
                "UPDATE GTM SET PPOE=?, POE=?, LBR=? WHERE fecha=?",
                ppoe, poe, lbr, row["fecha"]
            )
        else:
            cursor.execute(
                "INSERT INTO GTM (fecha, PPOE, POE, LBR) VALUES (?,?,?,?)",
                row["fecha"], ppoe, poe, lbr
            )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[GTM] {len(df)} filas guardadas.")
