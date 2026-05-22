"""
ETL CAISO extendido — extrae LMP + componentes (energy/congestion/loss)
y guarda en caiso.prices (nueva arquitectura).
Cubre DA y FMM para los nodos ROA y TJI.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import math
import time
import pandas as pd
from datetime import datetime, timedelta

from etl.base.db import get_connection
from etl.caiso.caiso_api import (
    _fetch_oasis_xml, _caiso_dt, _lmp_components_to_hourly
)
from etl.caiso.config import NODES, NODE_ALIASES


def _safe(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ── Extracción con componentes ────────────────────────────────────────────────

def extract_caiso_components(fecha_ini: str, fecha_fin: str, market: str = "DA") -> pd.DataFrame:
    """
    Extrae LMP + componentes (energy, congestion, loss) de CAISO OASIS.
    market: "DA" (DAM) o "FMM" (RTPD)
    Retorna DataFrame: fecha, node, market, lmp, energy, congestion, loss
    """
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    if market.upper() == "DA":
        queryname    = "PRC_LMP"
        market_run   = "DAM"
        version      = "1"
    else:
        queryname    = "PRC_RTPD_LMP"
        market_run   = "RTPD"
        version      = "3"

    all_frames = []

    for node in NODES:
        alias = NODE_ALIASES.get(node, node)
        cur = ini_dt
        while cur <= fin_dt:
            d  = cur.strftime("%Y-%m-%d")
            d1 = (cur + timedelta(days=1)).strftime("%Y-%m-%d")
            try:
                df = _fetch_oasis_xml(
                    queryname,
                    _caiso_dt(d,  hour=7),
                    _caiso_dt(d1, hour=7),
                    version=version,
                    market_run_id=market_run,
                    node=node,
                )
                if not df.empty:
                    components = _lmp_components_to_hourly(df)
                    if not components.empty:
                        components["node"]   = node
                        components["market"] = market.upper()
                        all_frames.append(components)
            except Exception as e:
                print(f"[CAISO components] {d} {node} {market} error: {e}")
            cur += timedelta(days=1)
            time.sleep(0.5)

    if not all_frames:
        return pd.DataFrame(columns=["fecha", "node", "market", "lmp", "energy", "congestion", "loss"])

    return pd.concat(all_frames, ignore_index=True)


def upsert_caiso_prices(df: pd.DataFrame) -> tuple[int, int]:
    """Inserta en caiso.prices (fact — no sobreescribir)."""
    if df.empty:
        return 0, 0

    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = upd = 0

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM caiso.prices WHERE fecha=? AND node=? AND market=?",
            row["fecha"], row["node"], row["market"]
        )
        if cursor.fetchone()[0]:
            pass  # facts: no sobreescribir
        else:
            cursor.execute("""
                INSERT INTO caiso.prices (fecha, node, market, lmp, energy, congestion, loss)
                VALUES (?,?,?,?,?,?,?)
            """,
                row["fecha"], row["node"], row["market"],
                _safe(row.get("lmp")), _safe(row.get("energy")),
                _safe(row.get("congestion")), _safe(row.get("loss"))
            )
            ins += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[CAISO prices] inserted={ins}")
    return ins, upd


def run_caiso_components_day(fecha: str):
    """Extrae DA + FMM componentes para un día y guarda en caiso.prices."""
    for market in ["DA", "FMM"]:
        df = extract_caiso_components(fecha, fecha, market)
        if not df.empty:
            upsert_caiso_prices(df)
            print(f"[CAISO] {fecha} {market}: {len(df)} filas OK")
