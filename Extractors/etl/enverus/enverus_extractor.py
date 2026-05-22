"""
ETL Enverus — extrae datos de Mosaic API y guarda en schema enverus.*.
Requiere ENVERUS_USERNAME + ENVERUS_PASSWORD en .env

Uso:
    python -m etl.enverus.enverus_extractor --fecha 2026-04-06
    python -m etl.enverus.enverus_extractor --backfill --desde 2025-01-01 --hasta 2026-04-06
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import math
import logging
import argparse
from datetime import date, timedelta

import pandas as pd

from etl.base.db import get_connection
from etl.enverus.config import SYNTHETIC_ENTITIES, SYNTHETIC_DATASETS

log = logging.getLogger(__name__)


def _safe(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ── Upserts genéricos ─────────────────────────────────────────────────────────

def _upsert_renewable_forecasts(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = 0
    for _, row in df.iterrows():
        cursor.execute(
            """SELECT COUNT(*) FROM enverus.renewable_forecasts
               WHERE fecha=? AND iso=? AND resource_type=? AND region=? AND model=?""",
            row["fecha"], row["iso"], row["resource_type"], row["region"], row["model"]
        )
        if cursor.fetchone()[0]:
            # forecasts: actualizar
            cursor.execute(
                """UPDATE enverus.renewable_forecasts SET gen_mw=?
                   WHERE fecha=? AND iso=? AND resource_type=? AND region=? AND model=?""",
                _safe(row["gen_mw"]), row["fecha"], row["iso"],
                row["resource_type"], row["region"], row["model"]
            )
        else:
            cursor.execute(
                """INSERT INTO enverus.renewable_forecasts
                   (fecha, iso, resource_type, region, model, gen_mw)
                   VALUES (?,?,?,?,?,?)""",
                row["fecha"], row["iso"], row["resource_type"],
                row["region"], row["model"], _safe(row["gen_mw"])
            )
            ins += 1
    conn.commit()
    cursor.close()
    conn.close()
    return ins, 0


def _upsert_outages(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = 0
    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM enverus.outages WHERE fecha=? AND iso=? AND outage_type=?",
            row["fecha"], row["iso"], row["outage_type"]
        )
        if cursor.fetchone()[0]:
            cursor.execute(
                "UPDATE enverus.outages SET capacity_mw=? WHERE fecha=? AND iso=? AND outage_type=?",
                _safe(row["capacity_mw"]), row["fecha"], row["iso"], row["outage_type"]
            )
        else:
            cursor.execute(
                "INSERT INTO enverus.outages (fecha,iso,outage_type,capacity_mw) VALUES (?,?,?,?)",
                row["fecha"], row["iso"], row["outage_type"], _safe(row["capacity_mw"])
            )
            ins += 1
    conn.commit()
    cursor.close()
    conn.close()
    return ins, 0


def _upsert_grid_conditions(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = 0
    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM enverus.grid_conditions WHERE fecha=? AND iso=?",
            row["fecha"], row["iso"]
        )
        if cursor.fetchone()[0]:
            cursor.execute(
                """UPDATE enverus.grid_conditions
                   SET frequency_hz=?, prc_mw=?, operating_reserves=?,
                       dam_lambda=?, sced_lambda=?
                   WHERE fecha=? AND iso=?""",
                _safe(row["frequency_hz"]), _safe(row["prc_mw"]),
                _safe(row["operating_reserves"]), _safe(row["dam_lambda"]),
                _safe(row["sced_lambda"]), row["fecha"], row["iso"]
            )
        else:
            cursor.execute(
                """INSERT INTO enverus.grid_conditions
                   (fecha,iso,frequency_hz,prc_mw,operating_reserves,dam_lambda,sced_lambda)
                   VALUES (?,?,?,?,?,?,?)""",
                row["fecha"], row["iso"],
                _safe(row["frequency_hz"]), _safe(row["prc_mw"]),
                _safe(row["operating_reserves"]), _safe(row["dam_lambda"]),
                _safe(row["sced_lambda"])
            )
            ins += 1
    conn.commit()
    cursor.close()
    conn.close()
    return ins, 0


def _upsert_price_forecasts(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = 0
    for _, row in df.iterrows():
        cursor.execute(
            """SELECT COUNT(*) FROM enverus.price_forecasts
               WHERE fecha=? AND iso=? AND node=? AND market=? AND forecast_type=?""",
            row["fecha"], row["iso"], row["node"], row["market"], row["forecast_type"]
        )
        if cursor.fetchone()[0]:
            cursor.execute(
                """UPDATE enverus.price_forecasts SET lmp=?, lmp_p25=?, lmp_p75=?
                   WHERE fecha=? AND iso=? AND node=? AND market=? AND forecast_type=?""",
                _safe(row["lmp"]), _safe(row["lmp_p25"]), _safe(row["lmp_p75"]),
                row["fecha"], row["iso"], row["node"], row["market"], row["forecast_type"]
            )
        else:
            cursor.execute(
                """INSERT INTO enverus.price_forecasts
                   (fecha,iso,node,market,forecast_type,lmp,lmp_p25,lmp_p75)
                   VALUES (?,?,?,?,?,?,?,?)""",
                row["fecha"], row["iso"], row["node"], row["market"],
                row["forecast_type"],
                _safe(row["lmp"]), _safe(row["lmp_p25"]), _safe(row["lmp_p75"])
            )
            ins += 1
    conn.commit()
    cursor.close()
    conn.close()
    return ins, 0


# ── Runner diario ─────────────────────────────────────────────────────────────

def run_enverus_morning(fecha: str):
    """
    Corrida matutina: extrae forecasts y datos operativos de ayer.
    Llama a todos los endpoints de Mosaic API.
    """
    from etl.enverus.mosaic_api import (
        get_wind_forecasts, get_solar_forecasts, get_load_forecasts,
        get_outages, get_grid_conditions, get_tie_flows, get_price_forecasts,
    )

    log.info(f"[Enverus] Iniciando corrida morning para {fecha}")

    extractors = [
        ("wind_forecasts",   get_wind_forecasts,   _upsert_renewable_forecasts),
        ("solar_forecasts",  get_solar_forecasts,  _upsert_renewable_forecasts),
        ("load_forecasts",   get_load_forecasts,   _upsert_renewable_forecasts),
        ("outages",          get_outages,           _upsert_outages),
        ("grid_conditions",  get_grid_conditions,  _upsert_grid_conditions),
    ]

    for name, extract_fn, upsert_fn in extractors:
        try:
            log.info(f"[Enverus] {name}...")
            df = extract_fn(fecha, fecha)
            if not df.empty:
                ins, _ = upsert_fn(df)
                log.info(f"[Enverus] {name}: {len(df)} filas, inserted={ins}")
            else:
                log.warning(f"[Enverus] {name}: sin datos")
        except Exception as e:
            log.error(f"[Enverus] {name} falló: {e}")

    # Price forecasts por nodo
    from etl.enverus.config import SYNTHETIC_ENTITIES
    for node in SYNTHETIC_ENTITIES:
        try:
            df = get_price_forecasts(fecha, fecha, node)
            if not df.empty:
                ins, _ = _upsert_price_forecasts(df)
                log.info(f"[Enverus] price_forecasts {node}: {len(df)} filas, inserted={ins}")
        except Exception as e:
            log.error(f"[Enverus] price_forecasts {node} falló: {e}")

    log.info(f"[Enverus] Corrida morning {fecha} completada")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    parser = argparse.ArgumentParser(description="ETL Enverus Mosaic")
    parser.add_argument("--fecha",    type=str, help="Fecha YYYY-MM-DD (default: ayer)")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--desde",    type=str)
    parser.add_argument("--hasta",    type=str)
    args = parser.parse_args()

    ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    if args.backfill:
        if not args.desde:
            parser.error("--backfill requiere --desde")
        ini = date.fromisoformat(args.desde)
        fin = date.fromisoformat(args.hasta or ayer)
        cur = ini
        while cur <= fin:
            run_enverus_morning(str(cur))
            cur += timedelta(days=1)
    else:
        fecha = args.fecha or ayer
        run_enverus_morning(fecha)
