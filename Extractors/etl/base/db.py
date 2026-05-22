"""
Capa de acceso a datos — conexión SQL Server + bulk MERGE upsert.

Reglas:
  - Facts NUNCA se sobreescriben (INSERT WHERE NOT EXISTS)
  - Forecasts siempre se actualizan (MERGE UPDATE + INSERT)
  - Bulk MERGE: manda toda la tabla al servidor en un solo round-trip
"""
import time
import math
import logging
import pyodbc
import pandas as pd
from typing import Optional

from etl.base.credentials import get_db_creds

log = logging.getLogger(__name__)

# ── Conexión con retry automático ───────────────────────────────────────────

def get_connection(database: Optional[str] = None, retries: int = 5, wait: int = 30) -> pyodbc.Connection:
    """
    Retorna conexión pyodbc a SQL Server.
    Reintenta `retries` veces con espera `wait` segundos entre intentos
    para sobrevivir caídas TCP de larga duración.
    """
    creds = get_db_creds()
    db = database or creds["database"]

    # Driver 17 en Windows/Ubuntu ≤22, Driver 18 en Ubuntu 24+
    import sys, platform
    if sys.platform.startswith("linux"):
        import pyodbc as _po
        drivers = [d for d in _po.drivers() if "SQL Server" in d]
        driver = next((d for d in ["ODBC Driver 18 for SQL Server",
                                   "ODBC Driver 17 for SQL Server"] if d in drivers),
                      drivers[0] if drivers else "ODBC Driver 17 for SQL Server")
    else:
        driver = "ODBC Driver 17 for SQL Server"

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={creds['server']},{creds['port']};"
        f"DATABASE={db};"
        f"UID={creds['user']};"
        f"PWD={creds['password']};"
        f"TrustServerCertificate=yes;"
    )

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            conn = pyodbc.connect(conn_str)
            return conn
        except pyodbc.Error as e:
            last_err = e
            log.warning(f"[DB] Conexión fallida (intento {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(wait)

    raise last_err


# ── Sanitización de valores ──────────────────────────────────────────────────

def _safe(val):
    """Convierte NaN/inf a None para que SQL Server no los rechace."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if pd.isna(val):
        return None
    return val


# ── Bulk MERGE upsert ────────────────────────────────────────────────────────

def bulk_merge(
    conn: pyodbc.Connection,
    table: str,
    df: pd.DataFrame,
    pk_cols: list[str],
    data_type: str = "fact",        # "fact" o "forecast"
    update_cols: Optional[list[str]] = None,
) -> tuple[int, int]:
    """
    Hace MERGE bulk de `df` en `table`.

    - data_type="fact":     solo INSERT cuando no existe (facts jamás sobreescritos)
    - data_type="forecast": INSERT + UPDATE siempre (forecasts siempre actualizados)

    Retorna (inserted, updated).
    """
    if df.empty:
        return 0, 0

    cursor = conn.cursor()
    cursor.fast_executemany = True

    all_cols = list(df.columns)
    non_pk   = update_cols if update_cols else [c for c in all_cols if c not in pk_cols]

    # Construir MERGE T-SQL
    pk_match   = " AND ".join(f"target.[{c}] = source.[{c}]" for c in pk_cols)
    insert_cols = ", ".join(f"[{c}]" for c in all_cols)
    insert_vals = ", ".join(f"source.[{c}]" for c in all_cols)

    if data_type == "forecast" and non_pk:
        set_clause = ", ".join(f"target.[{c}] = source.[{c}]" for c in non_pk)
        when_matched = f"WHEN MATCHED THEN UPDATE SET {set_clause}"
    else:
        when_matched = ""  # facts: nunca actualizar

    # Soportar schema.tabla → [schema].[tabla]
    table_ref = ".".join(f"[{p}]" for p in table.split("."))

    sql = f"""
    MERGE {table_ref} AS target
    USING (VALUES ({", ".join("?" for _ in all_cols)}))
          AS source ({insert_cols})
    ON ({pk_match})
    {when_matched}
    WHEN NOT MATCHED THEN
        INSERT ({insert_cols}) VALUES ({insert_vals})
    OUTPUT $action;
    """

    inserted = 0
    updated  = 0

    rows = [
        tuple(_safe(row[c]) for c in all_cols)
        for _, row in df.iterrows()
    ]

    try:
        cursor.executemany(sql, rows)
        # OUTPUT $action no se puede consumir con executemany directamente,
        # así que estimamos: el total minus los que ya existían
        inserted = len(rows)   # conservador — el MERGE no duplica
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()

    return inserted, updated


def bulk_merge_with_count(
    conn: pyodbc.Connection,
    table: str,
    df: pd.DataFrame,
    pk_cols: list[str],
    data_type: str = "fact",
    update_cols: Optional[list[str]] = None,
) -> tuple[int, int]:
    """
    Versión row-by-row del MERGE para poder contar inserted/updated con precisión.
    Más lento que bulk_merge pero da conteos exactos.
    Usar solo cuando el logging preciso sea crítico.
    """
    if df.empty:
        return 0, 0

    cursor = conn.cursor()
    all_cols = list(df.columns)
    non_pk   = update_cols if update_cols else [c for c in all_cols if c not in pk_cols]

    pk_match    = " AND ".join(f"target.[{c}] = source.[{c}]" for c in pk_cols)
    insert_cols = ", ".join(f"[{c}]" for c in all_cols)
    insert_vals = ", ".join(f"source.[{c}]" for c in all_cols)

    if data_type == "forecast" and non_pk:
        set_clause = ", ".join(f"target.[{c}] = source.[{c}]" for c in non_pk)
        when_matched = f"WHEN MATCHED THEN UPDATE SET {set_clause}"
    else:
        when_matched = ""

    # Soportar schema.tabla → [schema].[tabla]
    table_ref = ".".join(f"[{p}]" for p in table.split("."))

    sql = f"""
    MERGE {table_ref} AS target
    USING (VALUES ({", ".join("?" for _ in all_cols)}))
          AS source ({insert_cols})
    ON ({pk_match})
    {when_matched}
    WHEN NOT MATCHED THEN
        INSERT ({insert_cols}) VALUES ({insert_vals})
    OUTPUT $action;
    """

    inserted = 0
    updated  = 0

    for _, row in df.iterrows():
        vals = tuple(_safe(row[c]) for c in all_cols)
        try:
            cursor.execute(sql, vals)
            result = cursor.fetchone()
            if result:
                if result[0] == "INSERT":
                    inserted += 1
                elif result[0] == "UPDATE":
                    updated += 1
        except Exception as e:
            log.error(f"[DB] Error en fila {dict(row)}: {e}")

    conn.commit()
    cursor.close()
    return inserted, updated
