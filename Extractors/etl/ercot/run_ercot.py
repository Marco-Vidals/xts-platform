"""
Runner CLI para el ETL de ERCOT.

Uso:
    python run_ercot.py                          # ayer
    python run_ercot.py --backfill --desde 2026-01-01 --hasta 2026-03-22

Cron jobs sugeridos (servidor Linux):
    # Precios DA: disponibles ~14:00 CT del día de operación
    30 14 * * * cd /data/xts/etl && python -m etl.ercot.run_ercot

    # Backfill inicial: correr una sola vez
    # python -m etl.ercot.run_ercot --backfill --desde 2025-01-01 --hasta 2026-03-22
"""
import argparse
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from etl.ercot.ercot_extractor import extract_ercot, upsert_ercot


def main():
    parser = argparse.ArgumentParser(description="ETL ERCOT — DC_L, DC_R, Load, Wind")
    parser.add_argument("--backfill",  action="store_true",
                        help="Modo backfill (requiere --desde y --hasta)")
    parser.add_argument("--desde",    type=str, help="Fecha inicial YYYY-MM-DD")
    parser.add_argument("--hasta",    type=str, help="Fecha final   YYYY-MM-DD")
    args = parser.parse_args()

    if args.backfill:
        if not args.desde or not args.hasta:
            print("ERROR: --backfill requiere --desde y --hasta")
            sys.exit(1)
        fecha_ini = args.desde
        fecha_fin = args.hasta
    else:
        ayer = date.today() - timedelta(days=1)
        fecha_ini = fecha_fin = ayer.strftime("%Y-%m-%d")

    print(f"=== ETL ERCOT | {fecha_ini} → {fecha_fin} ===")
    df = extract_ercot(fecha_ini, fecha_fin)
    print(df.to_string(index=False))
    upsert_ercot(df)
    print("=== Listo ===")


if __name__ == "__main__":
    main()
