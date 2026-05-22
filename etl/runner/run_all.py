"""
ETL Master Runner — XTS Platform
Corre todos los extractores para un rango de fechas.

Uso:
    # Ayer (modo normal diario):
    python -m etl.runner.run_all

    # Backfill:
    python -m etl.runner.run_all --backfill --desde 2025-09-01 --hasta 2026-03-22

    # Solo un extractor:
    python -m etl.runner.run_all --solo ercot
    python -m etl.runner.run_all --solo gtm
    python -m etl.runner.run_all --solo temperaturas
    python -m etl.runner.run_all --solo tipo_cambio
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
import logging
from datetime import datetime, timedelta, date

# ── Logger ─────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, f"etl_{datetime.today().strftime('%Y-%m-%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
# Forzar UTF-8 en stdout para Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
log = logging.getLogger("run_all")


# ── Importación lazy (para que errores de import no bloqueen otros módulos) ─
def _import_ercot():
    from etl.ercot.ercot_extractor import extract_ercot, upsert_ercot
    return extract_ercot, upsert_ercot

def _import_gtm():
    from etl.guatemala.gtm_extractor import extract_gtm, upsert_gtm
    return extract_gtm, upsert_gtm

def _import_tc():
    from etl.common.tipo_cambio import extract_tipo_cambio, upsert_tipo_cambio
    return extract_tipo_cambio, upsert_tipo_cambio

def _import_temps():
    from etl.common.temperaturas import extract_temperaturas, upsert_temperaturas
    return extract_temperaturas, upsert_temperaturas

def _import_caiso():
    from etl.caiso.caiso_extractor import extract_caiso, upsert_caiso
    return extract_caiso, upsert_caiso


# ── Runners individuales ────────────────────────────────────────────────────
CHUNK_DAYS = 7   # días por request para APIs con límite

def _run_in_chunks(extract_fn, upsert_fn, fecha_ini: str, fecha_fin: str, nombre: str) -> bool:
    """Corre extract+upsert en chunks de CHUNK_DAYS días. Retorna True si ok."""
    ini = datetime.strptime(fecha_ini, "%Y-%m-%d").date()
    fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
    ok  = True

    cur = ini
    while cur <= fin:
        chunk_fin = min(cur + timedelta(days=CHUNK_DAYS - 1), fin)
        tag = f"{cur} → {chunk_fin}"
        try:
            log.info(f"[{nombre}] Extrayendo {tag}...")
            df = extract_fn(str(cur), str(chunk_fin))
            if df is not None and not df.empty:
                upsert_fn(df)
                log.info(f"[{nombre}] {tag} - {len(df)} filas ok")
            else:
                log.warning(f"[{nombre}] {tag} - sin datos")
        except Exception as e:
            log.error(f"[{nombre}] {tag} - ERROR: {e}")
            ok = False
        cur = chunk_fin + timedelta(days=1)

    return ok


def run_ercot(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_ercot()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "ERCOT")
    except Exception as e:
        log.error(f"[ERCOT] import error: {e}")
        return False


def run_gtm(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_gtm()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "GTM")
    except Exception as e:
        log.error(f"[GTM] import error: {e}")
        return False


def run_tipo_cambio(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_tc()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "TIPO_CAMBIO")
    except Exception as e:
        log.error(f"[TIPO_CAMBIO] import error: {e}")
        return False


def run_caiso(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_caiso()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "CAISO")
    except Exception as e:
        log.error(f"[CAISO] import error: {e}")
        return False


def run_temperaturas(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_temps()
        # Open-Meteo aguanta rangos largos
        try:
            log.info(f"[TEMPERATURAS] Extrayendo {fecha_ini} -> {fecha_fin}...")
            df = extract_fn(fecha_ini, fecha_fin)
            if df is not None and not df.empty:
                upsert_fn(df)
                log.info(f"[TEMPERATURAS] {len(df)} filas ok")
                return True
            else:
                log.warning("[TEMPERATURAS] sin datos")
                return False
        except Exception as e:
            log.error(f"[TEMPERATURAS] ERROR: {e}")
            return False
    except Exception as e:
        log.error(f"[TEMPERATURAS] import error: {e}")
        return False


# ── Runner principal ────────────────────────────────────────────────────────
EXTRACTORES = {
    "ercot":        run_ercot,
    "caiso":        run_caiso,
    "gtm":          run_gtm,
    "tipo_cambio":  run_tipo_cambio,
    "temperaturas": run_temperaturas,
}


def run_all(fecha_ini: str, fecha_fin: str, solo: str | None = None) -> dict[str, bool]:
    """
    Corre todos los extractores (o solo uno si `solo` está definido).
    Retorna dict {nombre: True/False}.
    """
    targets = {solo: EXTRACTORES[solo]} if solo else EXTRACTORES

    resultados = {}
    log.info(f"=== ETL START | {fecha_ini} -> {fecha_fin} | extractores: {list(targets.keys())} ===")

    for nombre, fn in targets.items():
        log.info(f"--- {nombre.upper()} ---")
        resultados[nombre] = fn(fecha_ini, fecha_fin)

    fallidos = [k for k, v in resultados.items() if not v]
    if fallidos:
        log.error(f"=== ETL COMPLETADO CON ERRORES: {fallidos} ===")
    else:
        log.info(f"=== ETL COMPLETADO OK ===")

    return resultados


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XTS ETL Master Runner")
    parser.add_argument("--backfill", action="store_true",
                        help="Modo backfill (requiere --desde y --hasta)")
    parser.add_argument("--desde",  type=str, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--hasta",  type=str, help="Fecha fin YYYY-MM-DD (default: ayer)")
    parser.add_argument("--solo",   type=str, choices=list(EXTRACTORES.keys()),
                        help="Correr solo un extractor")
    args = parser.parse_args()

    ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    if args.backfill:
        if not args.desde:
            parser.error("--backfill requiere --desde YYYY-MM-DD")
        fecha_ini = args.desde
        fecha_fin = args.hasta or ayer
    else:
        fecha_ini = args.desde or ayer
        fecha_fin = args.hasta or ayer

    resultados = run_all(fecha_ini, fecha_fin, solo=args.solo)

    # Exit code 1 si alguno falló
    if any(not v for v in resultados.values()):
        sys.exit(1)
