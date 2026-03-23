"""
Runner CLI para el ETL de Guatemala.

Uso:
    python run_gtm.py                            # ayer
    python run_gtm.py --backfill --desde 2025-09-01 --hasta 2026-03-22

Cron job sugerido (servidor Linux):
    # AMM publica el Excel del día en la madrugada (~00:30 CT)
    45 6 * * * cd /data/xts && python -m etl.guatemala.run_gtm
"""
import argparse
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from etl.guatemala.gtm_extractor import extract_gtm, upsert_gtm


def main():
    parser = argparse.ArgumentParser(description="ETL Guatemala — POE y LBR")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--desde",   type=str)
    parser.add_argument("--hasta",   type=str)
    args = parser.parse_args()

    if args.backfill:
        if not args.desde or not args.hasta:
            print("ERROR: --backfill requiere --desde y --hasta")
            sys.exit(1)
        fecha_ini, fecha_fin = args.desde, args.hasta
    else:
        ayer = date.today() - timedelta(days=1)
        fecha_ini = fecha_fin = ayer.strftime("%Y-%m-%d")

    print(f"=== ETL Guatemala | {fecha_ini} → {fecha_fin} ===")
    df = extract_gtm(fecha_ini, fecha_fin)
    print(df.head(5).to_string(index=False))
    upsert_gtm(df)
    print("=== Listo ===")


if __name__ == "__main__":
    main()
