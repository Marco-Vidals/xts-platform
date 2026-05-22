"""
Validaciones post-extracción — rangos de precios, completitud de horas, NaN.
Cada extractor puede llamar estas funciones desde su método validate().
"""
import math
import logging
import pandas as pd
from typing import Optional

log = logging.getLogger(__name__)

# ── Rangos esperados por mercado/tipo ────────────────────────────────────────

PRICE_RANGES = {
    "ercot_da":     (-500,  10_000),
    "ercot_rt":     (-500,  10_000),
    "cenace_mda":   (-500,   5_000),
    "cenace_mtr":   (-500,   5_000),
    "caiso_da":     (-500,   5_000),
    "caiso_fmm":    (-500,   5_000),
    "guatemala_poe": (0,       500),
    "guatemala_lbr": (0,       500),
}


def check_price_range(
    df: pd.DataFrame,
    price_col: str,
    market_key: str,
    warnings: list,
) -> None:
    """Verifica que los precios caigan dentro del rango esperado."""
    if price_col not in df.columns:
        return
    rng = PRICE_RANGES.get(market_key)
    if not rng:
        return
    lo, hi = rng
    series = df[price_col].dropna()
    if series.empty:
        return
    out_of_range = series[(series < lo) | (series > hi)]
    if not out_of_range.empty:
        warnings.append(
            f"[{price_col}] {len(out_of_range)} valores fuera de rango [{lo}, {hi}]: "
            f"min={series.min():.2f}, max={series.max():.2f}"
        )


def check_hourly_completeness(
    df: pd.DataFrame,
    fecha_col: str,
    fecha_ini: str,
    fecha_fin: str,
    warnings: list,
    tolerance: float = 0.10,  # tolerar hasta 10% faltantes (DST, etc.)
) -> None:
    """Verifica que el número de filas corresponda a las horas esperadas."""
    if fecha_col not in df.columns:
        return
    ini = pd.Timestamp(fecha_ini)
    fin = pd.Timestamp(fecha_fin) + pd.Timedelta(hours=23)
    expected = int((fin - ini).total_seconds() / 3600) + 1
    actual   = len(df)
    if actual < expected * (1 - tolerance):
        warnings.append(
            f"Completitud baja en [{fecha_col}]: "
            f"{actual}/{expected} horas ({actual/expected*100:.1f}%)"
        )


def check_no_nan(
    df: pd.DataFrame,
    cols: list[str],
    warnings: list,
    max_pct: float = 0.20,  # alertar si más del 20% son NaN
) -> None:
    """Verifica que las columnas críticas no tengan demasiados NaN."""
    for col in cols:
        if col not in df.columns:
            continue
        pct = df[col].isna().mean()
        if pct > max_pct:
            warnings.append(
                f"[{col}] {pct*100:.1f}% de valores son NaN "
                f"({df[col].isna().sum()}/{len(df)} filas)"
            )


def sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte float NaN/inf a None en todo el DataFrame.
    Llama antes de cualquier upsert para evitar errores SQL Server.
    """
    def _clean(val):
        if val is None:
            return None
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val

    return df.applymap(_clean)
