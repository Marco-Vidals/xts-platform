"""
Backfill inteligente de DATOS_ERCOT.

1) Corre check_gaps para identificar qué fechas tienen datos faltantes o NULLs.
2) Para cada fecha con problemas, corre extract_ercot + upsert_ercot
   (que ahora incluye fallback automático a Enverus para DC ties).
3) Al final vuelve a correr check_gaps para verificar que quedó limpio.
4) Si --adjacent-fallback, para fechas que siguen con problemas copia datos
   del día adyacente más cercano con datos completos (último recurso).

Uso:
    # Backfill solo de hoyos detectados (recomendado):
    python -m etl.ercot.run_backfill

    # Backfill forzado de un rango completo:
    python -m etl.ercot.run_backfill --desde 2025-09-01 --hasta 2026-05-05 --force

    # Solo verificar sin backfill:
    python -m etl.ercot.run_backfill --check-only

    # Backfill + fallback día adyacente para lo que no tenga fix via API:
    python -m etl.ercot.run_backfill --desde 2023-12-25 --hasta 2023-12-25 --force --adjacent-fallback
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
import time
import logging
import warnings
import pandas as pd
from datetime import date, timedelta, datetime

from etl.ercot.check_gaps      import check_gaps, print_report, get_dates_to_backfill, KEY_COLS
from etl.ercot.ercot_extractor import extract_ercot, upsert_ercot
from etl.common.db_connection  import get_connection

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f"backfill_ercot_{date.today()}.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("run_backfill")

CHUNK_DAYS  = 7    # días por extracción
SLEEP_SECS  = 3    # pausa entre chunks para no saturar APIs


def fill_from_adjacent(dates: list[str], max_lookback: int = 7) -> dict:
    """
    Último recurso: para cada fecha en `dates` que aún tenga NULLs o esté
    completamente ausente, copia datos del día adyacente más cercano con datos
    completos. Solo llena columnas que siguen NULL — no sobreescribe datos reales.

    Returns dict: {date_str -> source_date_str} para fechas que se pudieron rellenar.
    """
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    filled = {}

    # Carga todo el rango relevante para evaluar candidatos
    date_objs  = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
    lo = min(date_objs) - timedelta(days=max_lookback + 1)
    hi = max(date_objs) + timedelta(days=max_lookback + 1)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df_full = pd.read_sql(
            f"SELECT fecha, {', '.join(KEY_COLS)} FROM dbo.DATOS_ERCOT "
            f"WHERE fecha >= ? AND fecha < ?",
            conn,
            params=[f"{lo} 00:00", f"{hi + timedelta(days=1)} 00:00"],
        )

    if df_full.empty:
        log.warning("[adj] Sin datos en DB para buscar fuente adyacente.")
        conn.close()
        return filled

    df_full["fecha"] = pd.to_datetime(df_full["fecha"])
    df_full["_date"] = df_full["fecha"].dt.date
    df_full["_hr"]   = df_full["fecha"].dt.hour

    def _source_complete(src_date) -> bool:
        """True si src_date tiene 24 filas y todos los KEY_COLS no-NULL."""
        d = df_full[df_full["_date"] == src_date]
        if len(d) < 24:
            return False
        return all(d[c].notna().all() for c in KEY_COLS)

    for target_str in sorted(dates):
        target = datetime.strptime(target_str, "%Y-%m-%d").date()

        # Buscar fuente: día anterior primero, luego siguiente
        source = None
        for delta in range(1, max_lookback + 1):
            for candidate in [target - timedelta(days=delta),
                               target + timedelta(days=delta)]:
                if _source_complete(candidate):
                    source = candidate
                    break
            if source:
                break

        if not source:
            log.warning(f"[adj] {target_str}: no se encontro dia adyacente con datos completos.")
            continue

        delta_days = (target - source).days
        log.info(f"[adj] {target_str}: copiando de {source} (delta={delta_days:+d}d)")

        df_src = df_full[df_full["_date"] == source].copy()

        # ── Caso 1: fecha completamente ausente ─ INSERT ─────────────────────
        df_target_rows = df_full[df_full["_date"] == target]
        if df_target_rows.empty:
            for _, row in df_src.iterrows():
                nueva_fecha = row["fecha"] + pd.Timedelta(days=delta_days)
                vals = [nueva_fecha] + [
                    float(row[c]) if pd.notna(row[c]) else None for c in KEY_COLS
                ]
                ph = ", ".join("?" * len(vals))
                cursor.execute(
                    f"INSERT INTO DATOS_ERCOT (fecha, {', '.join(KEY_COLS)}) VALUES ({ph})",
                    *vals,
                )
            conn.commit()
            log.info(f"[adj] {target_str}: insertadas {len(df_src)} filas desde {source}.")
            filled[target_str] = str(source)
            continue

        # ── Caso 2: filas existen pero con NULLs ─ UPDATE solo cols NULL ─────
        # Detectar qué columnas siguen con NULLs en target
        null_cols = [c for c in KEY_COLS if df_target_rows[c].isna().any()]
        if not null_cols:
            log.info(f"[adj] {target_str}: ya no tiene NULLs, sin cambios.")
            continue

        # Construir mapa hora -> valores fuente
        src_map = {int(r["_hr"]): r for _, r in df_src.iterrows()}

        updates = 0
        for _, trow in df_target_rows.iterrows():
            hr      = int(trow["_hr"])
            srow    = src_map.get(hr)
            if srow is None:
                continue
            cols_to_upd = [c for c in null_cols if pd.isna(trow[c]) and pd.notna(srow[c])]
            if not cols_to_upd:
                continue
            sets = ", ".join(f"{c} = ?" for c in cols_to_upd)
            vals = [float(srow[c]) for c in cols_to_upd]
            cursor.execute(
                f"UPDATE DATOS_ERCOT SET {sets} WHERE fecha = ?",
                *vals, trow["fecha"],
            )
            updates += 1

        conn.commit()
        log.info(f"[adj] {target_str}: {updates} filas actualizadas "
                 f"(cols: {', '.join(null_cols)}) desde {source}.")
        filled[target_str] = str(source)

    cursor.close()
    conn.close()
    return filled


def _date_chunks(dates: list[str], chunk_size: int):
    """Agrupa fechas consecutivas en chunks para hacer extracciones por rango."""
    if not dates:
        return
    dates_sorted = sorted(set(dates))
    chunk_start  = dates_sorted[0]
    prev         = dates_sorted[0]

    for d in dates_sorted[1:]:
        from datetime import datetime
        d_dt    = datetime.strptime(d, "%Y-%m-%d").date()
        prev_dt = datetime.strptime(prev, "%Y-%m-%d").date()
        gap     = (d_dt - prev_dt).days

        # Cortar chunk si hay salto > 1 día o si el chunk ya tiene CHUNK_DAYS días
        chunk_start_dt = datetime.strptime(chunk_start, "%Y-%m-%d").date()
        chunk_len      = (d_dt - chunk_start_dt).days

        if gap > 1 or chunk_len >= chunk_size:
            yield chunk_start, prev
            chunk_start = d
        prev = d

    yield chunk_start, prev


def run_backfill(desde: str | None = None, hasta: str | None = None,
                 force: bool = False, check_only: bool = False,
                 adjacent_fallback: bool = False):
    ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    # ── 1. Verificación inicial ───────────────────────────────────────────────
    log.info("=== BACKFILL ERCOT — verificación inicial ===")
    report = check_gaps(desde, hasta)
    print_report(report)

    if check_only:
        return

    # ── 2. Determinar fechas a corregir ───────────────────────────────────────
    if force and desde:
        # Modo force: extrae todo el rango especificado
        ini = desde
        fin = hasta or ayer
        log.info(f"Modo --force: backfill completo {ini} -> {fin}")
        dates_to_fix = []
        cur = date.fromisoformat(ini)
        end = date.fromisoformat(fin)
        while cur <= end:
            dates_to_fix.append(str(cur))
            cur += timedelta(days=1)
    else:
        dates_to_fix = get_dates_to_backfill(report)
        # Limitar a rango especificado si se indicó
        if desde:
            dates_to_fix = [d for d in dates_to_fix if d >= desde]
        if hasta:
            dates_to_fix = [d for d in dates_to_fix if d <= hasta]

    if not dates_to_fix:
        log.info("OK No hay fechas que corregir. Base de datos perfecta.")
        return

    log.info(f"Fechas a backfill: {len(dates_to_fix)}")
    for d in dates_to_fix[:10]:
        log.info(f"  {d}")
    if len(dates_to_fix) > 10:
        log.info(f"  ... y {len(dates_to_fix) - 10} más")

    # ── 3. Backfill por chunks ────────────────────────────────────────────────
    ok_count  = 0
    err_count = 0

    for chunk_ini, chunk_fin in _date_chunks(dates_to_fix, CHUNK_DAYS):
        log.info(f"--- Procesando {chunk_ini} -> {chunk_fin} ---")
        try:
            df = extract_ercot(chunk_ini, chunk_fin)
            if df is not None and not df.empty:
                upsert_ercot(df)
                ok_count += 1
                log.info(f"  OK {chunk_ini} -> {chunk_fin} OK ({len(df)} filas)")
            else:
                log.warning(f"  FALLO {chunk_ini} -> {chunk_fin} — sin datos")
                err_count += 1
        except Exception as e:
            log.error(f"  FALLO {chunk_ini} -> {chunk_fin} — ERROR: {e}")
            err_count += 1

        time.sleep(SLEEP_SECS)

    log.info(f"\n=== Backfill completado: {ok_count} chunks OK, {err_count} con errores ===")

    # ── 4. Verificación final ─────────────────────────────────────────────────
    log.info("=== Verificación final ===")
    report_post = check_gaps(desde, hasta)
    print_report(report_post)

    remaining = get_dates_to_backfill(report_post)
    if remaining:
        log.warning(f"Aun quedan {len(remaining)} fechas con problemas:")
        for d in remaining[:20]:
            log.warning(f"  FALLO {d}")

        # ── 5. Fallback día adyacente (solo si --adjacent-fallback) ──────────
        if adjacent_fallback:
            log.info(f"=== Fallback dia adyacente para {len(remaining)} fechas ===")
            filled = fill_from_adjacent(remaining)
            if filled:
                log.info(f"Rellenas con dia adyacente ({len(filled)}):")
                for d, src in filled.items():
                    log.info(f"  {d} <- copiado de {src}")
            # Verificacion post-adjacent
            log.info("=== Verificacion post-adjacent ===")
            report_adj = check_gaps(desde, hasta)
            print_report(report_adj)
            still_bad = get_dates_to_backfill(report_adj)
            if still_bad:
                log.warning(f"Siguen con problemas ({len(still_bad)}): {still_bad[:10]}")
            else:
                log.info("OK Base de datos perfecta tras fallback adyacente.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill inteligente de DATOS_ERCOT")
    parser.add_argument("--desde",      type=str,  default=None,  help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--hasta",      type=str,  default=None,  help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--force",      action="store_true",       help="Forzar extracción de todo el rango")
    parser.add_argument("--check-only",        action="store_true", help="Solo verificar, no corregir")
    parser.add_argument("--adjacent-fallback", action="store_true",
                        help="Si quedan NULLs tras API, copiar del dia adyacente mas cercano (ultimo recurso)")
    args = parser.parse_args()

    run_backfill(
        desde             = args.desde,
        hasta             = args.hasta,
        force             = args.force,
        check_only        = args.check_only,
        adjacent_fallback = args.adjacent_fallback,
    )
