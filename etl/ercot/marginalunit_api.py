"""
Cliente para la API de MarginalUnit (api1.marginalunit.com).
Extrae pronósticos sintéticos (lmp_da, lmp_rt) para DC_L y DC_R en granularidad HORARIA.
"""
import os
import io
import requests
import pandas as pd
from datetime import timedelta

MU_ROOT = "https://api1.marginalunit.com/pr-forecast"
MU_AUTH = (
    os.environ.get("MU_USERNAME", "mvidals@xiix.mx"),
    os.environ.get("MU_PASSWORD", ""),
)


def _get(path: str, **params) -> pd.DataFrame:
    resp = requests.get(MU_ROOT + path, auth=MU_AUTH, params=params, timeout=60)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


def _latest_version(dataset: str, org: str = "ercot") -> str:
    df = _get("/synthetic/forecasts")
    mask = (df["org"] == org) & (df["dataset"] == dataset) & (df["is_latest"] == 1)
    versions = df.loc[mask, "version"].tolist()
    if not versions:
        raise ValueError(f"No hay versión activa para {org}/{dataset}")
    return versions[-1]


def _asofs(dataset: str, version: str, entities: str,
           org: str = "ercot") -> pd.DataFrame:
    df = _get(f"/synthetic/{org}/{dataset}/{version}/as_ofs", entities=entities)
    df["as_of_dt"] = pd.to_datetime(df["as_of"], utc=True)
    return df.sort_values("as_of_dt").reset_index(drop=True)


def _report(dataset: str, version: str, entities: str,
            as_of: str, org: str = "ercot") -> pd.DataFrame:
    df = _get(f"/synthetic/{org}/{dataset}/{version}/report",
              entities=entities, as_of=as_of)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


# ── Extracción horaria ────────────────────────────────────────────────────────
def get_forecast_hourly(dataset: str, entities: list[str],
                        fecha_ini: str, fecha_fin: str,
                        org: str = "ercot") -> pd.DataFrame:
    """
    Extrae pronóstico horario (mediana = synthetic_0_5) para cada entidad.
    Para cada hora en [fecha_ini, fecha_fin] usa el as_of publicado justo antes.

    Retorna df con columnas: fecha (datetime UTC), {entity}_fcst por entidad.
    """
    ent_str = ";".join(entities)
    version = _latest_version(dataset, org)
    df_asofs = _asofs(dataset, version, ent_str, org)

    ini_utc = pd.Timestamp(fecha_ini, tz="UTC")
    fin_utc = pd.Timestamp(fecha_fin, tz="UTC") + pd.Timedelta(hours=23)

    # ── Agrupar as_ofs en bloques de 48 h (lookahead del modelo) ─────────────
    # Para no hacer una llamada por hora, se agrupan las horas por el as_of
    # que aplica a cada una. Cada as_of cubre las próximas ~48 horas.
    # Mapeamos cada hora a su as_of más reciente publicado antes de esa hora.
    horas = pd.date_range(fecha_ini, fecha_fin + " 23:00", freq="h", tz="UTC")

    # as_of_dt ordenados ascendente
    asof_times = df_asofs["as_of_dt"].tolist()
    asof_strs  = df_asofs["as_of"].tolist()

    hora_to_asof: dict[pd.Timestamp, str] = {}
    for h in horas:
        # as_of publicado estrictamente antes de la hora
        candidatos = [(t, s) for t, s in zip(asof_times, asof_strs) if t < h]
        if candidatos:
            hora_to_asof[h] = candidatos[-1][1]

    if not hora_to_asof:
        return pd.DataFrame()

    # ── Descargar un reporte por as_of único ─────────────────────────────────
    asof_unicos = list(dict.fromkeys(hora_to_asof.values()))  # orden preservado
    reports: dict[str, pd.DataFrame] = {}
    for asof in asof_unicos:
        try:
            reports[asof] = _report(dataset, version, ent_str, asof, org)
        except Exception as e:
            print(f"[MU] report {asof} falló: {e}")

    # ── Armar DataFrame horario ───────────────────────────────────────────────
    rows = []
    for h in horas:
        asof = hora_to_asof.get(h)
        if asof is None or asof not in reports:
            continue
        rep = reports[asof]
        # Buscar la fila cuyo timestamp sea esta hora (tolerancia ±30 min)
        delta = (rep["timestamp"] - h).abs()
        idx   = delta.idxmin()
        if delta[idx] > pd.Timedelta(minutes=30):
            continue
        row = {"fecha": h}
        for ent in entities:
            df_ent = rep[rep["entity"] == ent]
            if df_ent.empty or "synthetic_0_5" not in df_ent.columns:
                row[f"{ent}_fcst"] = None
            else:
                # valor más cercano en tiempo
                d2 = (df_ent["timestamp"] - h).abs()
                row[f"{ent}_fcst"] = float(df_ent.loc[d2.idxmin(), "synthetic_0_5"])
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("fecha").reset_index(drop=True)
