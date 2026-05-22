"""
Carga credenciales desde .env (raíz del proyecto) o variables de entorno del sistema.
NUNCA hardcodear credenciales en código — todo va aquí.
"""
import os
from pathlib import Path


def _load_dotenv():
    """Lee el archivo .env si existe y lo carga en os.environ (sin dependencia externa)."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()


# ── SQL Server ──────────────────────────────────────────────────────────────
def get_db_creds() -> dict:
    return {
        "server":   os.environ.get("XTS_DB_SERVER",   "ec2-34-203-113-74.compute-1.amazonaws.com"),
        "port":     os.environ.get("XTS_DB_PORT",     "1433"),
        "user":     os.environ.get("XTS_DB_USER",     "sa"),
        "password": os.environ.get("XTS_DB_PASSWORD", ""),
        "database": os.environ.get("XTS_DB_NAME",     "XTS"),
    }


# ── ERCOT ───────────────────────────────────────────────────────────────────
def get_ercot_creds() -> dict:
    return {
        "username": os.environ.get("ERCOT_USERNAME", ""),
        "password": os.environ.get("ERCOT_PASSWORD", ""),
        "ocp_key":  os.environ.get("ERCOT_OCP_KEY",  ""),
    }


# ── CAISO ───────────────────────────────────────────────────────────────────
def get_caiso_creds() -> dict:
    return {
        "client_id":     os.environ.get("CAISO_CLIENT_ID",     ""),
        "client_secret": os.environ.get("CAISO_CLIENT_SECRET", ""),
    }


# ── Enverus ─────────────────────────────────────────────────────────────────
def get_enverus_creds() -> dict:
    return {
        "api_key":    os.environ.get("ENVERUS_API_KEY",    ""),
        "token":      os.environ.get("ENVERUS_TOKEN",      ""),
        "username":   os.environ.get("ENVERUS_USERNAME",   ""),
        "password":   os.environ.get("ENVERUS_PASSWORD",   ""),
    }


# ── MarginalUnit ────────────────────────────────────────────────────────────
def get_marginalunit_creds() -> dict:
    return {
        "api_key": os.environ.get("MARGINALUNIT_API_KEY", ""),
    }


# ── Email alertas ───────────────────────────────────────────────────────────
def get_email_creds() -> dict:
    return {
        "smtp_server":   os.environ.get("SMTP_SERVER",   "smtp.gmail.com"),
        "smtp_port":     int(os.environ.get("SMTP_PORT", "587")),
        "smtp_user":     os.environ.get("SMTP_USER",     ""),
        "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
        "alert_to":      os.environ.get("ALERT_EMAIL_TO", "").split(","),
    }
