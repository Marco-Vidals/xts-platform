"""
ETL Master Runner — XTS Platform

Uso:
    # Corrida diaria normal (ayer):
    python -m etl.runner.run_all --schedule morning
    python -m etl.runner.run_all --schedule afternoon

    # Backfill:
    python -m etl.runner.run_all --backfill --desde 2025-09-01 --hasta 2026-03-22

    # Solo un extractor:
    python -m etl.runner.run_all --solo ercot
    python -m etl.runner.run_all --solo gtm

    # Rango explícito:
    python -m etl.runner.run_all --desde 2026-04-01 --hasta 2026-04-06
"""
import sys
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
import logging
import smtplib
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText

# ── Logger ──────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, f"etl_{datetime.today().strftime('%Y-%m-%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
log = logging.getLogger("run_all")


# ── Importación lazy ─────────────────────────────────────────────────────────
def _import_ercot():
    from etl.ercot.ercot_extractor import extract_ercot, upsert_ercot
    return extract_ercot, upsert_ercot

def _import_ercot_prices():
    from etl.ercot.ercot_prices_extractor import extract_ercot_prices, upsert_ercot_prices
    return extract_ercot_prices, upsert_ercot_prices

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

def _import_cenace():
    from etl.cenace.run_cenace import run_cenace_day
    return run_cenace_day

def _import_ercot_extended():
    from etl.ercot.ercot_extended import (
        extract_fuel_mix, upsert_fuel_mix,
        extract_ordc, upsert_ordc,
        extract_ancillary, upsert_ancillary,
        extract_binding_constraints, upsert_binding_constraints,
    )
    return (extract_fuel_mix, upsert_fuel_mix, extract_ordc, upsert_ordc,
            extract_ancillary, upsert_ancillary,
            extract_binding_constraints, upsert_binding_constraints)

def _import_caiso_extended():
    from etl.caiso.caiso_extended import extract_caiso_components, upsert_caiso_prices
    return extract_caiso_components, upsert_caiso_prices

def _import_enverus():
    from etl.enverus.enverus_extractor import run_enverus_morning
    return run_enverus_morning

def _import_synthetic():
    from etl.enverus.synthetic_extractor import run_synthetic_day
    return run_synthetic_day


# ── Alertas email ────────────────────────────────────────────────────────────

def _send_alert(subject: str, body: str):
    try:
        from etl.base.credentials import get_email_creds
        creds = get_email_creds()
        if not creds["smtp_user"] or not creds["alert_to"]:
            return
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[XTS ETL ALERT] {subject}"
        msg["From"]    = creds["smtp_user"]
        msg["To"]      = ", ".join(creds["alert_to"])
        with smtplib.SMTP(creds["smtp_server"], creds["smtp_port"]) as s:
            s.starttls()
            s.login(creds["smtp_user"], creds["smtp_password"])
            s.sendmail(creds["smtp_user"], creds["alert_to"], msg.as_string())
        log.info(f"[ALERT] Email enviado: {subject}")
    except Exception as e:
        log.warning(f"[ALERT] No se pudo enviar email: {e}")


# ── Retry config por fuente ──────────────────────────────────────────────────
RETRY_CONFIG = {
    "cenace":    {"max_retries": 3, "backoff_seconds": 60},
    "ercot":     {"max_retries": 4, "backoff_seconds": 15},
    "caiso":     {"max_retries": 3, "backoff_seconds": 10},
    "enverus":   {"max_retries": 3, "backoff_seconds": 30},
    "guatemala": {"max_retries": 2, "backoff_seconds": 30},
    "default":   {"max_retries": 3, "backoff_seconds": 20},
}


# ── Runner genérico con retry y etl_log ─────────────────────────────────────
import time
CHUNK_DAYS = 7

def _run_in_chunks(
    extract_fn, upsert_fn, fecha_ini: str, fecha_fin: str,
    nombre: str, source_key: str = "default"
) -> bool:
    """Corre extract+upsert en chunks de CHUNK_DAYS días con retry por chunk."""
    from datetime import datetime as dt
    ini = dt.strptime(fecha_ini, "%Y-%m-%d").date()
    fin = dt.strptime(fecha_fin, "%Y-%m-%d").date()
    rc  = RETRY_CONFIG.get(source_key, RETRY_CONFIG["default"])
    ok  = True
    cur = ini

    while cur <= fin:
        chunk_fin = min(cur + timedelta(days=CHUNK_DAYS - 1), fin)
        tag = f"{cur} → {chunk_fin}"
        t0  = time.time()

        for attempt in range(1, rc["max_retries"] + 1):
            try:
                log.info(f"[{nombre}] Extrayendo {tag} (intento {attempt})...")
                df = extract_fn(str(cur), str(chunk_fin))
                if df is not None and not df.empty:
                    upsert_fn(df)
                    dur = round(time.time() - t0, 1)
                    log.info(f"[{nombre}] {tag} — {len(df)} filas ok ({dur}s)")
                    _write_etl_log(source_key, nombre, "SUCCESS", len(df), 0, 0,
                                   round(time.time() - t0, 2), None, str(cur), str(chunk_fin))
                else:
                    log.warning(f"[{nombre}] {tag} — sin datos")
                    _write_etl_log(source_key, nombre, "PARTIAL", 0, 0, 0,
                                   round(time.time() - t0, 2), "DataFrame vacío", str(cur), str(chunk_fin))
                break  # éxito
            except Exception as e:
                log.warning(f"[{nombre}] {tag} intento {attempt} falló: {e}")
                if attempt < rc["max_retries"]:
                    time.sleep(rc["backoff_seconds"])
                else:
                    log.error(f"[{nombre}] {tag} FALLÓ tras {rc['max_retries']} intentos: {e}")
                    _write_etl_log(source_key, nombre, "FAILED", 0, 0, 0,
                                   round(time.time() - t0, 2), str(e)[:2000], str(cur), str(chunk_fin))
                    ok = False

        cur = chunk_fin + timedelta(days=1)

    return ok


def _write_etl_log(
    source, extractor, status, rows_ext, rows_ins, rows_upd,
    duration_sec, error_msg, fecha_ini, fecha_fin
):
    try:
        from etl.base.db import get_connection
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.etl_log
                (source, extractor, status, rows_extracted, rows_inserted,
                 rows_updated, duration_sec, error_message, fecha_ini, fecha_fin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, source, extractor, status, rows_ext, rows_ins, rows_upd,
             duration_sec, error_msg, fecha_ini, fecha_fin)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        log.warning(f"[etl_log] No se pudo escribir: {e}")


# ── Runners individuales ─────────────────────────────────────────────────────

def run_ercot(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_ercot()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "ERCOT", "ercot")
    except Exception as e:
        log.error(f"[ERCOT] import error: {e}")
        return False


def run_ercot_prices(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_ercot_prices()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "ERCOT-PRICES", "ercot")
    except Exception as e:
        log.error(f"[ERCOT-PRICES] import error: {e}")
        return False


def run_gtm(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_gtm()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "GTM", "guatemala")
    except Exception as e:
        log.error(f"[GTM] import error: {e}")
        return False


def run_tipo_cambio(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_tc()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "TIPO_CAMBIO", "default")
    except Exception as e:
        log.error(f"[TIPO_CAMBIO] import error: {e}")
        return False


def run_caiso(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_caiso()
        return _run_in_chunks(extract_fn, upsert_fn, fecha_ini, fecha_fin, "CAISO", "caiso")
    except Exception as e:
        log.error(f"[CAISO] import error: {e}")
        return False


def run_temperaturas(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_temps()
        # Chunk en 30 días para evitar TCP drop en upsert de rangos grandes
        from datetime import datetime as dt
        ini = dt.strptime(fecha_ini, "%Y-%m-%d").date()
        fin = dt.strptime(fecha_fin, "%Y-%m-%d").date()
        ok  = True
        cur = ini
        while cur <= fin:
            chunk_fin = min(cur + timedelta(days=29), fin)
            t0 = time.time()
            try:
                log.info(f"[TEMPERATURAS] Extrayendo {cur} → {chunk_fin}...")
                df = extract_fn(str(cur), str(chunk_fin))
                if df is not None and not df.empty:
                    upsert_fn(df)
                    log.info(f"[TEMPERATURAS] {cur} → {chunk_fin}: {len(df)} filas ok ({round(time.time()-t0,1)}s)")
                    _write_etl_log("weather", "temperaturas", "SUCCESS", len(df), 0, 0,
                                    round(time.time()-t0, 2), None, str(cur), str(chunk_fin))
                else:
                    log.warning(f"[TEMPERATURAS] {cur} → {chunk_fin}: sin datos")
            except Exception as e:
                log.error(f"[TEMPERATURAS] {cur} → {chunk_fin} ERROR: {e}")
                _write_etl_log("weather", "temperaturas", "FAILED", 0, 0, 0,
                                round(time.time()-t0, 2), str(e)[:2000], str(cur), str(chunk_fin))
                ok = False
            cur = chunk_fin + timedelta(days=1)
        return ok
    except Exception as e:
        log.error(f"[TEMPERATURAS] import error: {e}")
        return False


def run_enverus(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        run_morning = _import_enverus()
        from datetime import datetime as dt
        ini = dt.strptime(fecha_ini, "%Y-%m-%d").date()
        fin = dt.strptime(fecha_fin, "%Y-%m-%d").date()
        ok  = True
        cur = ini
        while cur <= fin:
            try:
                log.info(f"[ENVERUS] Extrayendo {cur}...")
                run_morning(str(cur))
                log.info(f"[ENVERUS] {cur} ok")
            except Exception as e:
                log.error(f"[ENVERUS] {cur} ERROR: {e}")
                ok = False
            cur += timedelta(days=1)
        return ok
    except Exception as e:
        log.error(f"[ENVERUS] import error: {e}")
        return False


def run_ercot_extended(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        fns = _import_ercot_extended()
        ex_fuel, up_fuel, ex_ordc, up_ordc, ex_anc, up_anc, ex_bc, up_bc = fns
        ok = True
        # fuel_mix omitido — endpoint np3-966-er/gen_fuel_mix_rpt no disponible en API pública
        ok &= _run_in_chunks(ex_ordc,  up_ordc,  fecha_ini, fecha_fin, "ERCOT-ORDC",    "ercot")
        ok &= _run_in_chunks(lambda a,b: ex_anc(a,b,"DA"), up_anc, fecha_ini, fecha_fin, "ERCOT-ANC-DA", "ercot")
        ok &= _run_in_chunks(lambda a,b: ex_anc(a,b,"RT"), up_anc, fecha_ini, fecha_fin, "ERCOT-ANC-RT", "ercot")
        ok &= _run_in_chunks(ex_bc,    up_bc,    fecha_ini, fecha_fin, "ERCOT-BC",      "ercot")
        return ok
    except Exception as e:
        log.error(f"[ERCOT-EXT] import error: {e}")
        return False


def run_caiso_extended(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        extract_fn, upsert_fn = _import_caiso_extended()
        ok = True
        ok &= _run_in_chunks(lambda a,b: extract_fn(a,b,"DA"), upsert_fn, fecha_ini, fecha_fin, "CAISO-LMP-DA", "caiso")
        ok &= _run_in_chunks(lambda a,b: extract_fn(a,b,"RT"), upsert_fn, fecha_ini, fecha_fin, "CAISO-LMP-RT", "caiso")
        return ok
    except Exception as e:
        log.error(f"[CAISO-EXT] import error: {e}")
        return False


def run_synthetic(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        run_day = _import_synthetic()
        from datetime import datetime as dt
        ini = dt.strptime(fecha_ini, "%Y-%m-%d").date()
        fin = dt.strptime(fecha_fin, "%Y-%m-%d").date()
        ok  = True
        cur = ini
        while cur <= fin:
            try:
                log.info(f"[SYNTHETIC] Extrayendo {cur}...")
                run_day(str(cur))
                log.info(f"[SYNTHETIC] {cur} ok")
            except Exception as e:
                log.error(f"[SYNTHETIC] {cur} ERROR: {e}")
                ok = False
            cur += timedelta(days=1)
        return ok
    except Exception as e:
        log.error(f"[SYNTHETIC] import error: {e}")
        return False


def run_cenace(fecha_ini: str, fecha_fin: str) -> bool:
    try:
        run_cenace_day = _import_cenace()
        from datetime import datetime as dt
        ini = dt.strptime(fecha_ini, "%Y-%m-%d").date()
        fin = dt.strptime(fecha_fin, "%Y-%m-%d").date()
        ok = True
        cur = ini
        while cur <= fin:
            t0 = time.time()
            try:
                log.info(f"[CENACE] Extrayendo {cur}...")
                run_cenace_day(str(cur))
                dur = round(time.time() - t0, 2)
                log.info(f"[CENACE] {cur} ok ({dur}s)")
                _write_etl_log("cenace", "CENACE-PML", "SUCCESS", 0, 0, 0,
                               dur, None, str(cur), str(cur))
            except Exception as e:
                dur = round(time.time() - t0, 2)
                log.error(f"[CENACE] {cur} ERROR: {e}")
                _write_etl_log("cenace", "CENACE-PML", "ERROR", 0, 0, 0,
                               dur, str(e)[:2000], str(cur), str(cur))
                ok = False
            cur += timedelta(days=1)
        return ok
    except Exception as e:
        log.error(f"[CENACE] import error: {e}")
        return False


# ── Schedules ────────────────────────────────────────────────────────────────
# Corrida matutina: facts del día anterior (prioridad 1-5)
MORNING_EXTRACTORES = [
    ("ercot",          run_ercot,          1),
    ("ercot_prices",   run_ercot_prices,   1),
    ("caiso",          run_caiso,          1),
    ("gtm",            run_gtm,            1),
    ("tipo_cambio",    run_tipo_cambio,    2),
    ("temperaturas",   run_temperaturas,   5),
    ("cenace",         run_cenace,         1),
    ("caiso_extended", run_caiso_extended, 2),
    ("synthetic",      run_synthetic,      3),
    ("enverus",        run_enverus,        3),
    # ("ercot_extended", run_ercot_extended, 2),  # pendiente: endpoints ORDC/ANC/BC no disponibles en API pública
]

# Corrida de la tarde: solo forecasts y datos intradía
AFTERNOON_EXTRACTORES = [
    ("ercot",  run_ercot,  1),  # RT parcial del día en curso
]

# Mapa completo para --solo
EXTRACTORES = {
    "ercot":          run_ercot,
    "ercot_prices":   run_ercot_prices,
    "caiso":          run_caiso,
    "gtm":          run_gtm,
    "tipo_cambio":  run_tipo_cambio,
    "temperaturas": run_temperaturas,
    "cenace":       run_cenace,
    "enverus":         run_enverus,
    "synthetic":       run_synthetic,
    "ercot_extended":  run_ercot_extended,
    "caiso_extended":  run_caiso_extended,
}


# ── Runner principal ──────────────────────────────────────────────────────────
def run_all(
    fecha_ini: str,
    fecha_fin: str,
    solo: str | None = None,
    schedule: str | None = None,
) -> dict[str, bool]:
    """Corre extractores según schedule o todos. Retorna {nombre: True/False}."""
    if solo:
        targets = [(solo, EXTRACTORES[solo], 1)]
    elif schedule == "afternoon":
        targets = AFTERNOON_EXTRACTORES
    else:
        targets = MORNING_EXTRACTORES  # morning o default

    resultados = {}
    log.info(f"=== ETL START | schedule={schedule or 'manual'} | {fecha_ini} → {fecha_fin} | {[t[0] for t in targets]} ===")

    for nombre, fn, _prio in sorted(targets, key=lambda x: x[2]):
        log.info(f"--- {nombre.upper()} ---")
        resultados[nombre] = fn(fecha_ini, fecha_fin)

    fallidos = [k for k, v in resultados.items() if not v]
    if fallidos:
        log.error(f"=== ETL COMPLETADO CON ERRORES: {fallidos} ===")
        _send_alert(
            f"Extractores fallidos ({fecha_ini}→{fecha_fin})",
            f"Los siguientes extractores fallaron:\n\n" +
            "\n".join(f"  - {f}" for f in fallidos) +
            f"\n\nRevisa logs en: {log_file}"
        )
    else:
        log.info(f"=== ETL COMPLETADO OK ===")

    return resultados


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XTS ETL Master Runner")
    parser.add_argument("--schedule", type=str, choices=["morning", "afternoon", "maintenance"],
                        help="Tipo de corrida programada")
    parser.add_argument("--backfill", action="store_true",
                        help="Modo backfill (requiere --desde y --hasta)")
    parser.add_argument("--desde",   type=str, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--hasta",   type=str, help="Fecha fin YYYY-MM-DD (default: ayer)")
    parser.add_argument("--solo",    type=str, choices=list(EXTRACTORES.keys()),
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

    resultados = run_all(fecha_ini, fecha_fin, solo=args.solo, schedule=args.schedule)

    if any(not v for v in resultados.values()):
        sys.exit(1)
