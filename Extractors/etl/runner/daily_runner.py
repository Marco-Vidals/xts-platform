"""
Daily Runner — XTS Platform
Corre el ETL diario con retry automático.

Si el ETL falla:
  - Reintenta cada RETRY_INTERVAL_HOURS horas
  - Máximo MAX_RETRIES intentos
  - Envía alerta si todos los intentos fallan

Uso:
    # Correr manualmente:
    python -m etl.runner.daily_runner

    # Configurar Windows Task Scheduler para correr diario a las 7:30 AM:
    schtasks /create /tn "XTS ETL Diario" /tr "python -m etl.runner.daily_runner" /sc daily /st 07:30
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import smtplib
import logging
import json
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from etl.runner.run_all import run_all, log as run_log

# ── Configuración ─────────────────────────────────────────────────────────
RETRY_INTERVAL_HOURS = 2      # horas entre reintentos
MAX_RETRIES          = 5      # máximo de intentos por día
STATUS_FILE          = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "etl_status.json")

# Alertas de email (configurar en variables de entorno o aquí directamente)
ALERT_EMAIL_FROM  = os.environ.get("ALERT_EMAIL_FROM",  "")  # ej: xts.alerts@gmail.com
ALERT_EMAIL_TO    = os.environ.get("ALERT_EMAIL_TO",    "")  # ej: mvidals@xiix.mx
ALERT_EMAIL_PASS  = os.environ.get("ALERT_EMAIL_PASS",  "")  # app password de Gmail
ALERT_SMTP_HOST   = os.environ.get("ALERT_SMTP_HOST",   "smtp.gmail.com")
ALERT_SMTP_PORT   = int(os.environ.get("ALERT_SMTP_PORT", "587"))

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log = logging.getLogger("daily_runner")


# ── Estado persistente ─────────────────────────────────────────────────────
def _load_status() -> dict:
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_status(status: dict):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2, default=str)


# ── Alerta de email ────────────────────────────────────────────────────────
def send_alert(subject: str, body: str):
    """Envía email de alerta. Si no hay config de email, solo logea."""
    if not all([ALERT_EMAIL_FROM, ALERT_EMAIL_TO, ALERT_EMAIL_PASS]):
        log.warning(f"[ALERTA] Email no configurado. Mensaje: {subject}")
        log.warning(body)
        return

    try:
        msg = MIMEMultipart()
        msg["From"]    = ALERT_EMAIL_FROM
        msg["To"]      = ALERT_EMAIL_TO
        msg["Subject"] = f"[XTS ETL] {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(ALERT_SMTP_HOST, ALERT_SMTP_PORT) as srv:
            srv.starttls()
            srv.login(ALERT_EMAIL_FROM, ALERT_EMAIL_PASS)
            srv.sendmail(ALERT_EMAIL_FROM, ALERT_EMAIL_TO, msg.as_string())

        log.info(f"[ALERTA] Email enviado a {ALERT_EMAIL_TO}: {subject}")
    except Exception as e:
        log.error(f"[ALERTA] No se pudo enviar email: {e}")


def send_success_alert(fecha: str, resultados: dict):
    body = f"ETL completado correctamente para {fecha}.\n\n"
    for k, v in resultados.items():
        body += f"  • {k}: {'✓ OK' if v else '✗ FALLÓ'}\n"
    send_alert(f"✓ ETL OK — {fecha}", body)


def send_failure_alert(fecha: str, resultados: dict, intento: int):
    fallidos = [k for k, v in resultados.items() if not v]
    body = (
        f"El ETL del {fecha} FALLÓ en el intento #{intento}.\n\n"
        f"Extractores con error: {', '.join(fallidos)}\n\n"
        f"Se reintentará en {RETRY_INTERVAL_HOURS} horas "
        f"(máximo {MAX_RETRIES} intentos).\n\n"
        f"Revisa los logs en: logs/etl_{fecha}.log"
    )
    send_alert(f"✗ ETL FALLÓ intento {intento}/{MAX_RETRIES} — {fecha}", body)


def send_final_failure_alert(fecha: str, resultados: dict):
    fallidos = [k for k, v in resultados.items() if not v]
    body = (
        f"⚠️ ALERTA CRÍTICA: El ETL del {fecha} falló {MAX_RETRIES} veces.\n\n"
        f"Extractores con error: {', '.join(fallidos)}\n\n"
        f"Los datos de {fecha} NO se actualizaron.\n"
        f"Se requiere intervención manual.\n\n"
        f"Revisa los logs en: logs/etl_{fecha}.log"
    )
    send_alert(f"⚠️ ETL FALLÓ {MAX_RETRIES}x — INTERVENCIÓN REQUERIDA — {fecha}", body)


# ── Runner con retry ───────────────────────────────────────────────────────
def run_with_retry(fecha: str | None = None) -> bool:
    """
    Corre el ETL para `fecha` (o ayer si None).
    Reintenta hasta MAX_RETRIES veces con RETRY_INTERVAL_HOURS entre intentos.
    Retorna True si al menos un intento fue exitoso.
    """
    if fecha is None:
        fecha = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    status = _load_status()
    hoy = str(date.today())

    # Si ya completó hoy, no volver a correr
    if status.get("ultimo_ok") == hoy:
        log.info(f"ETL ya completado hoy ({hoy}). Nada que hacer.")
        return True

    for intento in range(1, MAX_RETRIES + 1):
        log.info(f"=== INTENTO {intento}/{MAX_RETRIES} — {fecha} ===")

        resultados = run_all(fecha, fecha)
        fallidos   = [k for k, v in resultados.items() if not v]

        if not fallidos:
            log.info(f"ETL completado OK en intento {intento}.")
            status.update({
                "ultimo_ok":      hoy,
                "ultimo_fecha":   fecha,
                "ultimo_intento": intento,
                "resultados":     resultados,
                "timestamp":      str(datetime.now()),
            })
            _save_status(status)
            if intento > 1:
                # Solo alertar si hubo reintentos (para no spam en el caso normal)
                send_success_alert(fecha, resultados)
            return True

        log.error(f"Intento {intento} falló: {fallidos}")
        status.update({
            "ultimo_error":   str(datetime.now()),
            "ultimo_intento": intento,
            "fallidos":       fallidos,
        })
        _save_status(status)

        if intento < MAX_RETRIES:
            send_failure_alert(fecha, resultados, intento)
            wait_secs = RETRY_INTERVAL_HOURS * 3600
            log.info(f"Esperando {RETRY_INTERVAL_HOURS}h antes de reintentar…")
            time.sleep(wait_secs)
        else:
            send_final_failure_alert(fecha, resultados)

    return False


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="XTS Daily ETL Runner con retry")
    parser.add_argument("--fecha", type=str, default=None,
                        help="Fecha a procesar YYYY-MM-DD (default: ayer)")
    parser.add_argument("--status", action="store_true",
                        help="Mostrar estado del último ETL y salir")
    args = parser.parse_args()

    if args.status:
        s = _load_status()
        if s:
            print(json.dumps(s, indent=2, default=str, ensure_ascii=False))
        else:
            print("Sin historial de ejecuciones.")
        sys.exit(0)

    ok = run_with_retry(args.fecha)
    sys.exit(0 if ok else 1)
