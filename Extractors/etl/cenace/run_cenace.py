"""
Runner del ETL CENACE - se ejecuta desde cron job.

Modos de uso:
  python run_cenace.py                  # Extrae ayer (modo diario normal)
  python run_cenace.py --proceso MDA    # Solo MDA de ayer
  python run_cenace.py --proceso MTR    # Solo MTR de ayer
  python run_cenace.py --backfill --desde 2023-01-01 --hasta 2024-12-31

Cron jobs recomendados (en el server Linux):
  # MDA: todos los dias a las 16:30 (CENACE publica ~15:30 hora MX)
  30 16 * * * cd /data/xts && python -m etl.cenace.run_cenace --proceso MDA

  # MTR: todos los dias a las 23:30 (cierre del dia)
  30 23 * * * cd /data/xts && python -m etl.cenace.run_cenace --proceso MTR
"""

import argparse
import logging
import sys
from datetime import date, timedelta

from etl.cenace.pml_extractor import extract_mda, extract_mtr, upsert_mda, upsert_mtr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_diario(proceso: str):
    """Extrae datos del dia anterior."""
    ayer = date.today() - timedelta(days=1)
    logger.info(f"Iniciando ETL CENACE {proceso} para {ayer}")

    if proceso in ("MDA", "AMBOS"):
        df = extract_mda(ayer, ayer)
        inserted = upsert_mda(df)
        logger.info(f"MDA {ayer}: {inserted} filas nuevas")

    if proceso in ("MTR", "AMBOS"):
        df = extract_mtr(ayer, ayer)
        inserted = upsert_mtr(df)
        logger.info(f"MTR {ayer}: {inserted} filas nuevas")


def run_backfill(proceso: str, fecha_ini: date, fecha_fin: date):
    """Llena datos historicos en ventanas de 7 dias."""
    logger.info(f"Iniciando backfill {proceso}: {fecha_ini} -> {fecha_fin}")

    current = fecha_ini
    while current <= fecha_fin:
        end = min(current + timedelta(days=6), fecha_fin)
        logger.info(f"  Procesando {current} - {end}")

        if proceso in ("MDA", "AMBOS"):
            df = extract_mda(current, end)
            upsert_mda(df)

        if proceso in ("MTR", "AMBOS"):
            df = extract_mtr(current, end)
            upsert_mtr(df)

        current = end + timedelta(days=1)

    logger.info("Backfill completado")


def run_cenace_day(fecha: str):
    """
    Punto de entrada para run_all.py — delega a cenace_extended.
    """
    from etl.cenace.cenace_extended import run_cenace_day as _run
    _run(fecha)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL CENACE PML")
    parser.add_argument("--proceso", choices=["MDA", "MTR", "AMBOS"], default="AMBOS")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--desde", type=str, help="Fecha inicio backfill YYYY-MM-DD")
    parser.add_argument("--hasta", type=str, help="Fecha fin backfill YYYY-MM-DD")
    args = parser.parse_args()

    if args.backfill:
        if not args.desde or not args.hasta:
            logger.error("--backfill requiere --desde y --hasta")
            sys.exit(1)
        fecha_ini = date.fromisoformat(args.desde)
        fecha_fin = date.fromisoformat(args.hasta)
        run_backfill(args.proceso, fecha_ini, fecha_fin)
    else:
        run_diario(args.proceso)
