"""
ETL CENACE extendido:
  - PML nodos P frontera → cenace.pml_nodos_p
  - PML zonas (108) → cenace.pml_zonas  (nueva arquitectura, paralelo a PML.dbo.MDA_D/MTR)
  - Función run_cenace_day() para integrar con run_all.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import math
import logging
from datetime import date, datetime, timedelta
from itertools import islice

import pandas as pd

from etl.base.db      import get_connection
from etl.cenace.config import NODOS_P_PRIORITARIOS, SISTEMAS
from etl.cenace.nodes_list import ZONAS
from etl.cenace.pml_extractor import (
    _fetch, _batches, _date_ranges,
    extract_mda, extract_mtr, upsert_mda, upsert_mtr,
    SLEEP_ENTRE_REQUESTS, MAX_NODOS,
)

log = logging.getLogger(__name__)


def _safe(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ── PML Zonas → cenace.pml_zonas ─────────────────────────────────────────────

def extract_pml_zonas(fecha_ini: date, fecha_fin: date, mercado: str = "MDA") -> pd.DataFrame:
    """
    Extrae PML para las 108 zonas CENACE (SIN + BCA + BCS).
    Guarda en cenace.pml_zonas (nueva arquitectura).
    Mercado: "MDA" o "MTR"
    """
    all_rows = []
    sistemas = {}
    for zona, sistema in ZONAS:
        sistemas.setdefault(sistema, []).append(zona)

    for sistema, zonas_sistema in sistemas.items():
        for batch in _batches(zonas_sistema, MAX_NODOS):
            for f_ini, f_fin in _date_ranges(fecha_ini, fecha_fin):
                rows = _fetch(sistema, mercado, batch, f_ini, f_fin)
                all_rows.extend(rows)
                time.sleep(SLEEP_ENTRE_REQUESTS)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    # Normalizar nombres de columnas según si es MDA o MTR
    if mercado == "MDA":
        col_map = {"pz": "pml", "pz_ene": "energia", "pz_per": "perdidas", "pz_cng": "congestion"}
    else:
        col_map = {"pml": "pml", "pml_ene": "energia", "pml_per": "perdidas", "pml_cng": "congestion"}

    for old, new in col_map.items():
        if old in df.columns:
            df[new] = df[old]

    df["hora"] = pd.to_numeric(df.get("hora", 1), errors="coerce").astype(int)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"]) + pd.to_timedelta(df["hora"] - 1, unit="h")
    else:
        return pd.DataFrame()

    df["sistema"]  = df.get("sistema", "SIN")
    df["zona"]     = df.get("clv_nodo", "")
    df["mercado"]  = mercado

    cols = ["fecha", "sistema", "zona", "mercado", "pml", "energia", "perdidas", "congestion"]
    for c in cols:
        if c not in df.columns:
            df[c] = None

    return df[cols].dropna(subset=["fecha", "zona"])


def upsert_pml_zonas(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    from etl.base.db import bulk_merge
    db = df.rename(columns={
        "energia":    "componente_energia",
        "congestion": "componente_congestion",
        "perdidas":   "componente_perdidas",
    })
    for c in ["pml", "componente_energia", "componente_congestion", "componente_perdidas"]:
        if c in db.columns:
            db[c] = db[c].apply(_safe)
    conn = get_connection("XTS")
    ins, upd = bulk_merge(
        conn, "cenace.pml_zonas", db,
        pk_cols=["fecha", "sistema", "zona", "mercado"],
        update_cols=["pml", "componente_energia", "componente_congestion", "componente_perdidas"],
    )
    conn.close()
    log.info(f"[cenace.pml_zonas] inserted={ins}, updated={upd}")
    return ins, upd


# ── PML Nodos P frontera → cenace.pml_nodos_p ────────────────────────────────

def extract_pml_nodos_p(fecha_ini: date, fecha_fin: date, mercado: str = "MDA") -> pd.DataFrame:
    """
    Extrae PML para los nodos P frontera (IVY, OMS, LAA, RRD, LBR, ENS, MXL).
    Lee la lista desde etl/cenace/config.py — extensible sin tocar este código.
    """
    all_rows = []

    for sistema, nodos in NODOS_P_PRIORITARIOS.items():
        for batch in _batches(nodos, MAX_NODOS):
            for f_ini, f_fin in _date_ranges(fecha_ini, fecha_fin):
                rows = _fetch(sistema, mercado, batch, f_ini, f_fin)
                # inyectar sistema en cada fila
                for r in rows:
                    r["sistema"] = sistema
                all_rows.extend(rows)
                time.sleep(SLEEP_ENTRE_REQUESTS)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    if mercado == "MDA":
        col_map = {"pz": "pml", "pz_ene": "energia", "pz_per": "perdidas", "pz_cng": "congestion"}
    else:
        col_map = {"pml": "pml", "pml_ene": "energia", "pml_per": "perdidas", "pml_cng": "congestion"}

    for old, new in col_map.items():
        if old in df.columns:
            df[new] = df[old]

    df["hora"] = pd.to_numeric(df.get("hora", 1), errors="coerce").astype(int)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"]) + pd.to_timedelta(df["hora"] - 1, unit="h")
    else:
        return pd.DataFrame()

    df["nodo"]    = df.get("clv_nodo", "")
    df["mercado"] = mercado

    cols = ["fecha", "nodo", "mercado", "pml", "energia", "perdidas", "congestion"]
    for c in cols:
        if c not in df.columns:
            df[c] = None

    return df[cols].dropna(subset=["fecha", "nodo"])


def upsert_pml_nodos_p(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    from etl.base.db import bulk_merge
    db = df.rename(columns={
        "energia":    "componente_energia",
        "congestion": "componente_congestion",
        "perdidas":   "componente_perdidas",
    })
    for c in ["pml", "componente_energia", "componente_congestion", "componente_perdidas"]:
        if c in db.columns:
            db[c] = db[c].apply(_safe)
    conn = get_connection("XTS")
    ins, upd = bulk_merge(
        conn, "cenace.pml_nodos_p", db,
        pk_cols=["fecha", "nodo", "mercado"],
        update_cols=["pml", "componente_energia", "componente_congestion", "componente_perdidas"],
    )
    conn.close()
    log.info(f"[cenace.pml_nodos_p] inserted={ins}, updated={upd}")
    return ins, upd


# ── Runner diario para integrar con run_all.py ────────────────────────────────

def run_cenace_day(fecha: str):
    """
    Extrae PML nodos P frontera (MDA + MTR) para un día dado.
    Guarda en cenace.pml_nodos_p (nueva arquitectura).

    NOTA: cenace.pml_zonas deshabilitado — el API SWPML solo acepta códigos de nodo físico
    (07IVY-230, 06LAA-138, etc.); consultas por nombre de zona (ACAPULCO, etc.)
    devuelven ZERO_RESULTS en todos los rangos de fechas.
    """
    d = date.fromisoformat(fecha)

    # Nodos P frontera (IVY, OMS, ENS, MXL, TIJ, LAA, RRD, LBR)
    try:
        df_p_mda = extract_pml_nodos_p(d, d, "MDA")
        upsert_pml_nodos_p(df_p_mda)
        df_p_mtr = extract_pml_nodos_p(d, d, "MTR")
        upsert_pml_nodos_p(df_p_mtr)
    except Exception as e:
        log.warning(f"[CENACE] cenace.pml_nodos_p falló (no crítico): {e}")

    log.info(f"[CENACE] {fecha} completado")
