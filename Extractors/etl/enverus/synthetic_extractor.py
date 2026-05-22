"""
ETL Synthetic Forecasts (MarginalUnit API) → enverus.synthetic_forecasts

Guarda TODOS los as_of (historial de forecasts) para backtesting.
Extrae percentiles completos: p05, p33, p50, p66, p95.
Datasets: lmp_da, lmp_rt, as_da, as_rt, rtrdpa
Entities: DC_L, DC_R (+ las que estén en config.py)

Uso:
    python -m etl.enverus.synthetic_extractor --fecha 2026-04-06
    python -m etl.enverus.synthetic_extractor --backfill --desde 2025-01-01 --hasta 2026-04-06
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import math
import logging
import argparse
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests
import io

log = logging.getLogger(__name__)

# ── MarginalUnit API client (mismo que marginalunit_api.py pero con todos los percentiles) ─

MU_ROOT = "https://api1.marginalunit.com/pr-forecast"


def _mu_auth():
    from etl.base.credentials import get_marginalunit_creds
    creds = get_marginalunit_creds()
    # Si no hay API key, usar usuario/password del .env
    if creds.get("api_key"):
        return None  # Bearer token si lo agregan después
    user = os.environ.get("MU_USERNAME", "")
    pwd  = os.environ.get("MU_PASSWORD", "")
    if not user:
        raise ValueError("MU_USERNAME no configurado en .env")
    return (user, pwd)


def _mu_get(path: str, **params) -> pd.DataFrame:
    auth = _mu_auth()
    resp = requests.get(MU_ROOT + path, auth=auth, params=params, timeout=60)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


def _latest_version(dataset: str, org: str = "ercot") -> str:
    df = _mu_get("/synthetic/forecasts")
    mask = (df["org"] == org) & (df["dataset"] == dataset) & (df["is_latest"] == 1)
    versions = df.loc[mask, "version"].tolist()
    if not versions:
        raise ValueError(f"No hay versión activa para {org}/{dataset}")
    return versions[-1]


def _get_asofs(dataset: str, version: str, entities: str, org: str = "ercot") -> pd.DataFrame:
    df = _mu_get(f"/synthetic/{org}/{dataset}/{version}/as_ofs", entities=entities)
    df["as_of_dt"] = pd.to_datetime(df["as_of"], utc=True)
    return df.sort_values("as_of_dt").reset_index(drop=True)


def _get_report(dataset: str, version: str, entities: str, as_of: str, org: str = "ercot") -> pd.DataFrame:
    df = _mu_get(
        f"/synthetic/{org}/{dataset}/{version}/report",
        entities=entities, as_of=as_of
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


# ── Extracción con todos los percentiles ─────────────────────────────────────

PERCENTILE_COLS = {
    "synthetic_0_05": "p05",
    "synthetic_0_33": "p33",
    "synthetic_0_5":  "p50",
    "synthetic_0_66": "p66",
    "synthetic_0_95": "p95",
}


def extract_synthetic(
    dataset: str,
    entities: list[str],
    fecha_ini: str,
    fecha_fin: str,
    org: str = "ercot",
    max_asofs: int = 6,
) -> pd.DataFrame:
    """
    Extrae los últimos max_asofs publicados que cubren el rango fecha_ini→fecha_fin.
    Para ETL diario usa max_asofs=6 (6 revisiones horarias). Para backfill usa None.
    Retorna df: fecha, dataset, entity, as_of, p05, p33, p50, p66, p95
    """
    ent_str = ",".join(entities)
    version = _latest_version(dataset, org)
    df_asofs = _get_asofs(dataset, version, ent_str, org)

    ini_utc = pd.Timestamp(fecha_ini, tz="UTC")
    fin_utc = pd.Timestamp(fecha_fin, tz="UTC") + pd.Timedelta(hours=23)

    # Filtrar as_ofs publicados antes del fin del día (para incluir los publicados durante el día)
    relevant = df_asofs[df_asofs["as_of_dt"] >= ini_utc - pd.Timedelta(hours=26)]
    relevant = relevant[relevant["as_of_dt"] <= fin_utc]

    if relevant.empty:
        log.warning(f"[Synthetic] {dataset} no tiene as_ofs para {fecha_ini}→{fecha_fin}")
        return pd.DataFrame()

    # Obtener as_of únicos (un sola llamada por timestamp, no por entity×timestamp)
    unique_asofs = (relevant.groupby("as_of")["as_of_dt"]
                   .first()
                   .sort_values()
                   .index.tolist())
    # Para ETL diario: solo los últimos N as_ofs (evitar miles de llamadas API)
    if max_asofs and len(unique_asofs) > max_asofs:
        unique_asofs = unique_asofs[-max_asofs:]

    log.debug(f"[Synthetic] {dataset}: {len(unique_asofs)} as_ofs a procesar")

    rows = []
    for asof_str in unique_asofs:
        try:
            report = _get_report(dataset, version, ent_str, asof_str, org)
        except Exception as e:
            log.warning(f"[Synthetic] {dataset} as_of={asof_str} falló: {e}")
            continue

        # Filtrar solo las horas dentro del rango
        report = report[report["timestamp"].dt.tz_localize(None) >= pd.Timestamp(fecha_ini)]
        report = report[report["timestamp"].dt.tz_localize(None) <= pd.Timestamp(fecha_fin) + pd.Timedelta(hours=23)]

        for _, r in report.iterrows():
            entity = r.get("entity", "")
            if entities and entity not in entities:
                continue
            row = {
                "fecha":   r["timestamp"].tz_localize(None) if hasattr(r["timestamp"], "tz_localize") else r["timestamp"],
                "dataset": dataset,
                "entity":  entity,
                "as_of":   pd.to_datetime(asof_str),
            }
            for api_col, our_col in PERCENTILE_COLS.items():
                row[our_col] = float(r[api_col]) if api_col in r and pd.notna(r[api_col]) else None
            rows.append(row)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── Upsert ────────────────────────────────────────────────────────────────────

def upsert_synthetic(df: pd.DataFrame) -> tuple[int, int]:
    """
    Inserta en enverus.synthetic_forecasts.
    Mantiene TODOS los as_of — no sobreescribir, solo insertar.
    PK: (fecha, dataset, entity, as_of)
    """
    if df.empty:
        return 0, 0
    from etl.base.db import get_connection, bulk_merge
    conn = get_connection("XTS")
    ins, upd = bulk_merge(
        conn, "enverus.synthetic_forecasts", df,
        pk_cols=["fecha", "dataset", "entity", "as_of"],
        update_cols=["p05", "p33", "p50", "p66", "p95"],
    )
    conn.close()
    dataset = df["dataset"].iloc[0] if not df.empty else ""
    log.info(f"[Synthetic] {dataset} inserted={ins}")
    return ins, upd


# ── Runner diario ─────────────────────────────────────────────────────────────

def run_synthetic_day(fecha: str):
    """Extrae todos los datasets sintéticos para una fecha."""
    from etl.enverus.config import SYNTHETIC_ENTITIES, SYNTHETIC_DATASETS

    for dataset in SYNTHETIC_DATASETS:
        try:
            log.info(f"[Synthetic] {dataset} {fecha}...")
            df = extract_synthetic(dataset, SYNTHETIC_ENTITIES, fecha, fecha)
            if not df.empty:
                ins, _ = upsert_synthetic(df)
                log.info(f"[Synthetic] {dataset}: {len(df)} filas, inserted={ins}")
            else:
                log.warning(f"[Synthetic] {dataset} {fecha}: sin datos")
        except Exception as e:
            log.error(f"[Synthetic] {dataset} {fecha} falló: {e}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    parser = argparse.ArgumentParser(description="ETL Synthetic Forecasts (MarginalUnit)")
    parser.add_argument("--fecha",    type=str)
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--desde",    type=str)
    parser.add_argument("--hasta",    type=str)
    args = parser.parse_args()

    ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    if args.backfill:
        ini = date.fromisoformat(args.desde or ayer)
        fin = date.fromisoformat(args.hasta or ayer)
        cur = ini
        while cur <= fin:
            run_synthetic_day(str(cur))
            cur += timedelta(days=1)
    else:
        run_synthetic_day(args.fecha or ayer)
