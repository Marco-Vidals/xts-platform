"""
ETL ERCOT Prices — extrae precios DA/RT para todos los hubs en SETTLEMENT_POINTS
y los guarda en ercot.prices (fecha, node, market, lmp).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import math
import pandas as pd

from etl.base.db         import get_connection
from etl.ercot.ercot_api import get_token, get_da_prices, get_rt_prices
from etl.ercot.config    import SETTLEMENT_POINTS

NODES = SETTLEMENT_POINTS["hubs"]  # ["DC_L", "DC_R", "HB_BUSAVG", "HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]


def extract_ercot_prices(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae precios DA y RT para todos los hubs.
    Retorna DataFrame con columnas: fecha, node, market, lmp
    """
    print(f"[ERCOT-PRICES] Obteniendo token...")
    token = get_token()
    rows = []

    for node in NODES:
        print(f"[ERCOT-PRICES] DA {node} {fecha_ini} -> {fecha_fin}")
        try:
            df_da = get_da_prices(token, fecha_ini, fecha_fin, node)
            for _, r in df_da.iterrows():
                rows.append({"fecha": r["fecha"], "node": node, "market": "DA", "lmp": r["precio_hora"]})
        except Exception as e:
            print(f"[ERCOT-PRICES] DA {node} falló: {e}")

        print(f"[ERCOT-PRICES] RT {node} {fecha_ini} -> {fecha_fin}")
        try:
            df_rt = get_rt_prices(token, fecha_ini, fecha_fin, node)
            for _, r in df_rt.iterrows():
                rows.append({"fecha": r["fecha"], "node": node, "market": "RT", "lmp": r["precio_hora"]})
        except Exception as e:
            print(f"[ERCOT-PRICES] RT {node} falló: {e}")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def _safe(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def upsert_ercot_prices(df: pd.DataFrame) -> None:
    """Upsert en ercot.prices usando MERGE por (fecha, node, market)."""
    if df.empty:
        print("[ERCOT-PRICES] Sin datos para guardar.")
        return

    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = upd = 0

    for _, row in df.iterrows():
        lmp = _safe(row["lmp"])
        cursor.execute(
            "SELECT COUNT(*) FROM ercot.prices WHERE fecha=? AND node=? AND market=?",
            row["fecha"], row["node"], row["market"]
        )
        existe = cursor.fetchone()[0]
        if existe:
            if lmp is not None:
                cursor.execute(
                    "UPDATE ercot.prices SET lmp=? WHERE fecha=? AND node=? AND market=?",
                    lmp, row["fecha"], row["node"], row["market"]
                )
                upd += 1
        else:
            cursor.execute(
                "INSERT INTO ercot.prices (fecha, node, market, lmp) VALUES (?,?,?,?)",
                row["fecha"], row["node"], row["market"], lmp
            )
            ins += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[ERCOT-PRICES] {ins} insertados, {upd} actualizados en ercot.prices.")
