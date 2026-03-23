"""
Cliente para la API de MarginalUnit (api1.marginalunit.com).
Extrae pronósticos sintéticos (lmp_da, lmp_rt) para DC_L y DC_R.
"""
import os
import requests
import pandas as pd
from datetime import datetime, timedelta

MU_ROOT    = "https://api1.marginalunit.com/pr-forecast"
MU_USER    = os.environ.get("MU_USERNAME", "mvidals@xiix.mx")
MU_PASS    = os.environ.get("MU_PASSWORD", "Cocochou1305#")
MU_AUTH    = (MU_USER, MU_PASS)

# ── Catálogo de versiones ─────────────────────────────────────────────────────
def _get_latest_version(dataset: str, org: str = "ercot") -> str:
    """Retorna la versión más reciente (is_latest=1) de un dataset."""
    resp = requests.get(f"{MU_ROOT}/synthetic/forecasts", auth=MU_AUTH, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(__import__("io").StringIO(resp.text))
    mask = (df["org"] == org) & (df["dataset"] == dataset) & (df["is_latest"] == 1)
    versions = df.loc[mask, "version"].tolist()
    if not versions:
        raise ValueError(f"No hay versión activa para {org}/{dataset}")
    return versions[-1]


# ── as_ofs disponibles ────────────────────────────────────────────────────────
def _get_asofs(dataset: str, version: str, entities: str,
               org: str = "ercot") -> pd.DataFrame:
    """Lista de fechas de publicación disponibles para las entidades dadas."""
    resp = requests.get(
        f"{MU_ROOT}/synthetic/{org}/{dataset}/{version}/as_ofs",
        auth=MU_AUTH,
        params={"entities": entities},
        timeout=30,
    )
    resp.raise_for_status()
    df = pd.read_csv(__import__("io").StringIO(resp.text))
    df["as_of_dt"] = pd.to_datetime(df["as_of"], utc=True)
    return df.sort_values("as_of_dt")


# ── Reporte de pronóstico ─────────────────────────────────────────────────────
def _get_report(dataset: str, version: str, entities: str,
                as_of: str, org: str = "ercot") -> pd.DataFrame:
    resp = requests.get(
        f"{MU_ROOT}/synthetic/{org}/{dataset}/{version}/report",
        auth=MU_AUTH,
        params={"entities": entities, "as_of": as_of},
        timeout=60,
    )
    resp.raise_for_status()
    df = pd.read_csv(__import__("io").StringIO(resp.text))
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


# ── Extracción principal ──────────────────────────────────────────────────────
def get_forecast_daily(dataset: str, entities: list[str],
                       fecha_ini: str, fecha_fin: str,
                       org: str = "ercot") -> pd.DataFrame:
    """
    Extrae pronóstico diario (mediana = synthetic_0_5) para una lista de entidades.
    Para cada fecha en [fecha_ini, fecha_fin], usa el as_of publicado el día anterior.

    Retorna df con columnas: fecha, {entity}_fcst para cada entity.
    """
    ent_str = ";".join(entities)
    version = _get_latest_version(dataset, org)

    # Obtener todas las fechas de publicación disponibles
    df_asofs = _get_asofs(dataset, version, ent_str, org)

    # Rango de fechas objetivo
    fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")

    # Para cada fecha, buscar el as_of más reciente que sea < esa fecha (DA)
    results = []
    for fecha in fechas:
        fecha_utc = pd.Timestamp(fecha, tz="UTC")
        # as_ofs publicados antes del inicio del día objetivo
        candidatos = df_asofs[df_asofs["as_of_dt"] < fecha_utc]
        if candidatos.empty:
            continue
        best_asof = candidatos.iloc[-1]["as_of"]

        df_rep = _get_report(dataset, version, ent_str, best_asof, org)
        # Filtrar solo las horas del día objetivo
        df_day = df_rep[df_rep["timestamp"].dt.date == fecha.date()]
        if df_day.empty:
            continue

        row = {"fecha": fecha.date()}
        for ent in entities:
            df_ent = df_day[df_day["entity"] == ent]
            if df_ent.empty or "synthetic_0_5" not in df_ent.columns:
                row[f"{ent}_fcst"] = None
            else:
                row[f"{ent}_fcst"] = df_ent["synthetic_0_5"].mean()
        results.append(row)

    if not results:
        return pd.DataFrame()

    df_out = pd.DataFrame(results)
    df_out["fecha"] = pd.to_datetime(df_out["fecha"])
    return df_out
