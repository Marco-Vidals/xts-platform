"""
Verifica la integridad de XTS.dbo.DATOS_ERCOT.

Reporta:
  - Rango de fechas en la tabla
  - Fechas completamente ausentes (no hay ninguna fila)
  - Fechas con menos de 24 horas
  - Columnas clave con NULLs por fecha

Uso:
    python -m etl.ercot.check_gaps
    python -m etl.ercot.check_gaps --desde 2025-09-01
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
import warnings
import pandas as pd
from datetime import date, timedelta

from etl.common.db_connection import get_connection

KEY_COLS = ["DA_DCL", "DA_DCR", "RT_DCL", "RT_DCR", "LOAD_ERCOT", "WIND_ERCOT"]


def check_gaps(desde: str | None = None, hasta: str | None = None) -> dict:
    """
    Analiza DATOS_ERCOT y retorna dict con:
      - fecha_min, fecha_max: rango real en la tabla
      - missing_dates: fechas sin ninguna fila
      - incomplete_dates: fechas con < 24 horas
      - null_summary: {col: [fechas con algún NULL]}
    """
    conn = get_connection("XTS")
    if conn is None:
        print("ERROR: No se pudo conectar a la BD.")
        return {}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_sql(
            f"""
            SELECT fecha, DA_DCL, DA_DCR, RT_DCL, RT_DCR,
                   LOAD_ERCOT, WIND_ERCOT
            FROM dbo.DATOS_ERCOT
            ORDER BY fecha
            """,
            conn,
        )
    conn.close()

    if df.empty:
        print("DATOS_ERCOT está vacía.")
        return {}

    df["fecha"] = pd.to_datetime(df["fecha"])
    df["date"]  = df["fecha"].dt.date

    fecha_min = df["date"].min()
    fecha_max = df["date"].max()

    # Aplicar filtro de rango si se especificó
    if desde:
        fecha_min_filtro = pd.to_datetime(desde).date()
        df = df[df["date"] >= fecha_min_filtro]
    if hasta:
        fecha_max_filtro = pd.to_datetime(hasta).date()
        df = df[df["date"] <= fecha_max_filtro]

    rango_desde = pd.to_datetime(desde).date() if desde else fecha_min
    rango_hasta = pd.to_datetime(hasta).date() if hasta else fecha_max

    # ── Fechas completamente ausentes ─────────────────────────────────────────
    fechas_esperadas = set(
        rango_desde + timedelta(days=i)
        for i in range((rango_hasta - rango_desde).days + 1)
    )
    fechas_presentes = set(df["date"].unique())
    missing_dates    = sorted(fechas_esperadas - fechas_presentes)

    # ── Fechas con menos de 24 horas ──────────────────────────────────────────
    horas_por_dia  = df.groupby("date").size()
    incomplete     = horas_por_dia[horas_por_dia < 24]
    incomplete_dates = {str(d): int(n) for d, n in incomplete.items()}

    # ── NULLs por columna y fecha ─────────────────────────────────────────────
    null_summary = {}
    for col in KEY_COLS:
        if col not in df.columns:
            null_summary[col] = ["columna no existe"]
            continue
        nulls = df[df[col].isna()]["date"].unique()
        if len(nulls):
            null_summary[col] = sorted(str(d) for d in nulls)

    return {
        "fecha_min":        str(fecha_min),
        "fecha_max":        str(fecha_max),
        "total_filas":      len(df),
        "rango_analizado":  f"{rango_desde} -> {rango_hasta}",
        "missing_dates":    [str(d) for d in missing_dates],
        "incomplete_dates": incomplete_dates,
        "null_summary":     null_summary,
    }


def print_report(r: dict):
    if not r:
        return
    print("\n" + "="*65)
    print("  REPORTE DE INTEGRIDAD — DATOS_ERCOT")
    print("="*65)
    print(f"  Rango en BD  : {r['fecha_min']} -> {r['fecha_max']}")
    print(f"  Rango analiz : {r['rango_analizado']}")
    print(f"  Total filas  : {r['total_filas']}")

    print(f"\n  Fechas completamente ausentes ({len(r['missing_dates'])}):")
    if r["missing_dates"]:
        for d in r["missing_dates"]:
            print(f"    FALTA {d}")
    else:
        print("    OK Ninguna")

    print(f"\n  Fechas con < 24 horas ({len(r['incomplete_dates'])}):")
    if r["incomplete_dates"]:
        for d, n in sorted(r["incomplete_dates"].items()):
            print(f"    FALTA {d}  ->  {n}/24 horas")
    else:
        print("    OK Ninguna")

    print(f"\n  NULLs por columna:")
    any_nulls = False
    for col in KEY_COLS:
        dates_with_nulls = r["null_summary"].get(col, [])
        if dates_with_nulls:
            any_nulls = True
            print(f"    {col}: {len(dates_with_nulls)} fechas con NULLs")
            for d in dates_with_nulls[:5]:
                print(f"      - {d}")
            if len(dates_with_nulls) > 5:
                print(f"      ... y {len(dates_with_nulls)-5} más")
        else:
            print(f"    {col}: OK completo")

    print("\n" + "="*65)
    total_issues = (len(r["missing_dates"]) + len(r["incomplete_dates"])
                    + sum(len(v) for v in r["null_summary"].values()))
    if total_issues == 0:
        print("  OK  BASE DE DATOS PERFECTA — sin hoyos detectados")
    else:
        print(f"  FALTA  Se encontraron problemas. Corre el backfill para corregirlos.")
    print("="*65 + "\n")


def get_dates_to_backfill(r: dict) -> list[str]:
    """Devuelve lista de fechas (YYYY-MM-DD) que necesitan backfill."""
    bad = set()
    bad.update(r.get("missing_dates", []))
    bad.update(r.get("incomplete_dates", {}).keys())
    for col_dates in r.get("null_summary", {}).values():
        if col_dates and col_dates[0] != "columna no existe":
            bad.update(col_dates)
    return sorted(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verifica integridad de DATOS_ERCOT")
    parser.add_argument("--desde", type=str, default=None, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--hasta", type=str, default=None, help="Fecha fin YYYY-MM-DD")
    args = parser.parse_args()

    report = check_gaps(args.desde, args.hasta)
    print_report(report)
