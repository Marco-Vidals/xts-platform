import pyodbc
import os


def _load_env_once():
    """Carga Extractors/.env si XTS_DB_SERVER no está ya en el entorno."""
    if os.environ.get("XTS_DB_SERVER"):
        return
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "Extractors", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "Extractors", ".env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip(); v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            break


_load_env_once()


def get_connection(database="XTS"):
    """
    Retorna conexion a SQL Server usando variables de entorno o valores por defecto.

    Variables de entorno:
        XTS_DB_SERVER   - hostname o IP del servidor (default: 100.70.216.12)
        XTS_DB_PORT     - puerto (default: 1433)
        XTS_DB_USER     - usuario (default: xts_app)
        XTS_DB_PASSWORD - password
    """
    server = os.environ.get("XTS_DB_SERVER", "100.70.216.12")
    port = os.environ.get("XTS_DB_PORT", "1433")
    user = os.environ.get("XTS_DB_USER", "sa")
    password = os.environ.get("XTS_DB_PASSWORD", "")

    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)
