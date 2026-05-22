"""
BaseExtractor — clase abstracta que deben heredar todos los extractores XTS.

Contrato:
  1. extract(fecha_ini, fecha_fin) → pd.DataFrame
  2. upsert(df)
  3. run(fecha_ini, fecha_fin) = extract + validate + upsert + log en etl_log

data_type:
  "fact"     → los datos históricos NUNCA se sobreescriben
  "forecast" → siempre se actualiza con el valor más reciente
"""
import time
import logging
import traceback
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)


class BaseExtractor(ABC):

    # Subclases DEBEN definir estos atributos
    source: str       = ""   # "ercot", "caiso", "cenace", etc.
    name: str         = ""   # "da_prices", "rt_prices", etc.
    data_type: str    = "fact"   # "fact" o "forecast"
    table: str        = ""   # "dbo.DATOS_ERCOT", "ercot.prices", etc.
    pk_cols: list     = []   # columnas que forman la PK para MERGE

    # Retry config por defecto — cada fuente puede sobreescribir
    max_retries: int  = 3
    retry_wait:  int  = 30   # segundos entre reintentos

    def __init__(self):
        self.log = logging.getLogger(f"{self.source}.{self.name}")

    # ── Interfaz abstracta ────────────────────────────────────────────────────

    @abstractmethod
    def extract(self, fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
        """Extrae datos de la fuente y retorna DataFrame limpio."""
        ...

    @abstractmethod
    def upsert(self, df: pd.DataFrame) -> tuple[int, int]:
        """
        Persiste el DataFrame en SQL Server.
        Retorna (inserted, updated).
        """
        ...

    # ── Validaciones ──────────────────────────────────────────────────────────

    def validate(self, df: pd.DataFrame, fecha_ini: str, fecha_fin: str) -> list[str]:
        """
        Valida el DataFrame post-extracción.
        Retorna lista de warnings (vacía = todo ok).
        Subclases pueden sobreescribir para validaciones específicas.
        """
        warnings = []
        if df is None or df.empty:
            warnings.append("DataFrame vacío")
            return warnings

        # Verificar completitud de horas (si hay columna fecha/hora)
        fecha_col = None
        for c in ["fecha", "FECHA", "datetime", "timestamp"]:
            if c in df.columns:
                fecha_col = c
                break

        if fecha_col:
            ini = pd.Timestamp(fecha_ini)
            fin = pd.Timestamp(fecha_fin) + pd.Timedelta(hours=23)
            expected_hours = int((fin - ini).total_seconds() / 3600) + 1
            actual_rows    = len(df)
            if actual_rows < expected_hours * 0.9:  # tolerar hasta 10% faltantes
                warnings.append(
                    f"Completitud baja: {actual_rows}/{expected_hours} filas esperadas"
                )

        return warnings

    # ── Runner principal ──────────────────────────────────────────────────────

    def run(
        self,
        fecha_ini: str,
        fecha_fin: str,
        log_to_db: bool = True,
    ) -> dict:
        """
        Pipeline completo: extract → validate → upsert → log.
        Retorna dict con status, rows, duración, errores.
        """
        t0 = time.time()
        result = {
            "source":        self.source,
            "extractor":     self.name,
            "status":        "FAILED",
            "rows_extracted": 0,
            "rows_inserted":  0,
            "rows_updated":   0,
            "duration_sec":   0,
            "error_message":  None,
            "fecha_ini":      fecha_ini,
            "fecha_fin":      fecha_fin,
        }

        df = None
        last_err = None

        # Retry loop
        for attempt in range(1, self.max_retries + 1):
            try:
                self.log.info(f"Extract {fecha_ini} → {fecha_fin} (intento {attempt})")
                df = self.extract(fecha_ini, fecha_fin)
                break  # éxito
            except Exception as e:
                last_err = e
                self.log.warning(f"Extract falló (intento {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_wait)
                else:
                    result["error_message"] = str(e)
                    result["duration_sec"] = round(time.time() - t0, 2)
                    self._log_to_db(result, log_to_db)
                    return result

        if df is None or df.empty:
            result["status"] = "PARTIAL"
            result["error_message"] = "DataFrame vacío tras extracción"
            result["duration_sec"] = round(time.time() - t0, 2)
            self._log_to_db(result, log_to_db)
            return result

        result["rows_extracted"] = len(df)

        # Validación
        warnings = self.validate(df, fecha_ini, fecha_fin)
        if warnings:
            for w in warnings:
                self.log.warning(f"Validación: {w}")

        # Upsert
        try:
            inserted, updated = self.upsert(df)
            result["rows_inserted"] = inserted
            result["rows_updated"]  = updated
            result["status"]        = "SUCCESS"
            self.log.info(
                f"Upsert OK — inserted={inserted}, updated={updated}, "
                f"rows={len(df)}, {fecha_ini}→{fecha_fin}"
            )
        except Exception as e:
            result["error_message"] = str(e)
            self.log.error(f"Upsert falló: {e}\n{traceback.format_exc()}")

        result["duration_sec"] = round(time.time() - t0, 2)
        self._log_to_db(result, log_to_db)
        return result

    # ── Log a etl_log ─────────────────────────────────────────────────────────

    def _log_to_db(self, result: dict, enabled: bool):
        if not enabled:
            return
        try:
            from etl.base.db import get_connection
            conn   = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dbo.etl_log
                    (source, extractor, status, rows_extracted, rows_inserted,
                     rows_updated, duration_sec, error_message, fecha_ini, fecha_fin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                result["source"], result["extractor"], result["status"],
                result["rows_extracted"], result["rows_inserted"],
                result["rows_updated"], result["duration_sec"],
                result["error_message"],
                result["fecha_ini"], result["fecha_fin"],
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            # No dejar que el logging falle el run
            self.log.warning(f"No se pudo escribir en etl_log: {e}")
