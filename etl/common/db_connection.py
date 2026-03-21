import pyodbc
import os


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
    user = os.environ.get("XTS_DB_USER", "xts_app")
    password = os.environ.get("XTS_DB_PASSWORD", "XTS@App2024!")

    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)
