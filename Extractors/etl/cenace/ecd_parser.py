"""
Parser de Estados de Cuenta CENACE (ECD CSV).
Adaptado de File reader 2.4.py para uso en produccion.

Uso:
    from etl.cenace.ecd_parser import parse_ecd_files
    result = parse_ecd_files(date(2026,3,14), date(2026,3,16))
    result.keys() -> ['xiix_facturas', 'cenace_facturas', 'xiix_reliq', 'cenace_reliq']
"""
import os, csv, time
import pandas as pd
from datetime import date, timedelta
from pandas.tseries.offsets import DateOffset, Week

ECD_BASE = os.path.join(
    os.path.expanduser("~"),
    "OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV",
    "XTS R&D", "Facturacion",
)

_CUENTAS_ORDEN = [
    "BCA-M024ERO", "BCA-M024ETJ", "BCA-M024IRO", "BCA-M024ITJ",
    "SIN-M024ELA", "SIN-M024ERD", "SIN-M024EGT", "SIN-M024IGT",
]

_COL_SCHEMA = ["FULS", "FUF", "CONCEPTO_DE_PAGO", "PRECIO",
               "CANTIDAD", "IMPORTE", "IVA", "TOTAL"]


def file_list(fecha_ini: date, fecha_fin: date) -> list[str]:
    """Rutas de todos los ECD CSV para el rango."""
    paths = []
    cur = fecha_ini
    while cur <= fecha_fin:
        yr = cur.strftime("%Y")
        mm = cur.strftime("%m")
        dd = cur.strftime("%d")
        for cuenta in _CUENTAS_ORDEN:
            p = os.path.join(ECD_BASE, yr, mm, dd, f"EC{yr}{mm}{dd}{cuenta}.csv")
            if os.path.exists(p):
                paths.append(p)
        cur += timedelta(days=1)
    return paths


def _parse_single(filepath: str) -> tuple:
    """
    Parsea un archivo ECD CSV.
    Retorna (df_xiix_factura, df_cenace_factura, df_xiix_reliq, df_cenace_reliq).
    Cada uno puede ser DataFrame vacio si no hay datos.
    """
    first_item, alldata = [], []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            first_item.append(str(row[0]))
            alldata.append([str(item) for item in row])
    first_item += ["FUF", "2"]

    # Localizar bloques FULS y FUF
    fuls, fufs = [], []
    for i in range(len(first_item)):
        if first_item[i] == "FULS" and i + 1 < len(first_item) and first_item[i + 1][:1] == "2":
            fuls.append(i)
        if first_item[i] == "FUF" and i > 0 and first_item[i - 1][:1] == "2":
            fufs.append((i, first_item[i + 1] if i + 1 < len(first_item) else ""))

    empty = pd.DataFrame(columns=_COL_SCHEMA)

    if len(fuls) < 2 or len(fufs) < 3:
        return empty, empty, empty, empty

    def _make_df(start_fuls_idx, end_fufs_idx, fuf_val):
        sr = fuls[start_fuls_idx]
        er = fufs[end_fufs_idx][0]
        cols = alldata[sr]
        df = pd.DataFrame(alldata[sr + 1: er], columns=cols)
        df.insert(1, "FUF", fuf_val)
        df["TOTAL"] = pd.to_numeric(df.get("TOTAL", 0), errors="coerce")
        return df[df["TOTAL"] != 0]

    df1 = _make_df(0, 1, fufs[0][1])   # XiiX facturas originales
    df2 = _make_df(1, 2, fufs[1][1])   # CENACE facturas originales

    # Reliquidaciones
    df3_xiix   = pd.DataFrame(columns=_COL_SCHEMA)
    df4_cenace = pd.DataFrame(columns=_COL_SCHEMA)

    for k in range(len(fuls) - 2):
        idx = k + 2
        if idx >= len(fuls) or idx + 1 >= len(fufs):
            break
        sr   = fuls[idx]
        er   = fufs[idx + 1][0]
        cols = alldata[sr]
        df   = pd.DataFrame(alldata[sr + 1: er], columns=cols)
        fuf_val = first_item[sr - 1] if sr > 0 else ""
        df.insert(1, "FUF", fuf_val)

        participante = alldata[sr - 1][1] if sr > 0 and len(alldata[sr - 1]) > 1 else ""
        if "XIIX" in participante.upper():
            df3_xiix = pd.concat([df3_xiix, df], ignore_index=True)
        elif "CENACE" in participante.upper() or "CENTRO NACIONAL" in participante.upper():
            df4_cenace = pd.concat([df4_cenace, df], ignore_index=True)

    for df in (df3_xiix, df4_cenace):
        if "TOTAL" in df.columns:
            df["TOTAL"] = pd.to_numeric(df["TOTAL"], errors="coerce")

    df3_xiix   = df3_xiix[df3_xiix.get("TOTAL", pd.Series()) != 0] if not df3_xiix.empty else df3_xiix
    df4_cenace = df4_cenace[df4_cenace.get("TOTAL", pd.Series()) != 0] if not df4_cenace.empty else df4_cenace

    return df1, df2, df3_xiix, df4_cenace


def parse_ecd_files(fecha_ini: date, fecha_fin: date) -> dict:
    """
    Parsea todos los ECD CSV del rango.

    Returns dict:
      xiix_facturas   -> DataFrame facturas originales XiiX
      cenace_facturas -> DataFrame facturas originales CENACE
      xiix_reliq      -> DataFrame reliquidaciones XiiX
      cenace_reliq    -> DataFrame reliquidaciones CENACE
      files_found     -> int cantidad de archivos procesados
      files_missing   -> list rutas no encontradas
    """
    files   = file_list(fecha_ini, fecha_fin)
    missing = []

    # Determinar archivos esperados (para reportar faltantes)
    cur = fecha_ini
    while cur <= fecha_fin:
        yr, mm, dd = cur.strftime("%Y"), cur.strftime("%m"), cur.strftime("%d")
        for cuenta in _CUENTAS_ORDEN:
            p = os.path.join(ECD_BASE, yr, mm, dd, f"EC{yr}{mm}{dd}{cuenta}.csv")
            if not os.path.exists(p):
                missing.append(p)
        cur += timedelta(days=1)

    _cols = _COL_SCHEMA
    accum = {k: pd.DataFrame(columns=_cols)
             for k in ("xiix_facturas", "cenace_facturas", "xiix_reliq", "cenace_reliq")}

    for fp in files:
        try:
            df1, df2, df3, df4 = _parse_single(fp)
            # Tag con el archivo fuente
            for df, key in [(df1, "xiix_facturas"), (df2, "cenace_facturas"),
                            (df3, "xiix_reliq"),    (df4, "cenace_reliq")]:
                df["_file"] = os.path.basename(fp)
                accum[key] = pd.concat([accum[key], df], ignore_index=True)
        except Exception as e:
            print(f"[ECD parser] Error en {fp}: {e}")
        time.sleep(0.01)

    # Limpiar tipos numericos
    for key in accum:
        for col in ("PRECIO", "CANTIDAD", "IMPORTE", "IVA", "TOTAL"):
            if col in accum[key].columns:
                accum[key][col] = pd.to_numeric(accum[key][col], errors="coerce")

    accum["files_found"]   = len(files)
    accum["files_missing"] = missing
    return accum


def _next_wednesday_after_sunday(d):
    """Logica de fecha limite de pago: siguiente domingo + siguiente miercoles + 1 semana."""
    from pandas.tseries.offsets import DateOffset, Week
    dt = pd.Timestamp(d)
    if dt.weekday() != 6:
        dt = dt + DateOffset(weekday=6)
    nw = dt + DateOffset(weekday=2)
    return nw + Week(weekday=2)


def build_facturas_format(df_xiix: pd.DataFrame, df_reliq: pd.DataFrame) -> tuple:
    """
    Genera los DataFrames en formato de factura/nota listo para exportar.
    Retorna (df_facturas, df_notas).
    """
    if df_xiix.empty:
        return pd.DataFrame(), pd.DataFrame()

    def _parse_periodo(fuf_series):
        return pd.to_datetime(fuf_series.str[:8], format="%Y%m%d", errors="coerce")

    # ── Facturas originales ───────────────────────────────────────────────────
    df_f = df_xiix.copy()
    df_f["Periodo ECD"] = _parse_periodo(df_f["FUF"])
    df_f["Fecha Limite"] = df_f["Periodo ECD"].apply(_next_wednesday_after_sunday)
    df_f["Participante"] = df_f["FUF"].str[8:15] if "FUF" in df_f.columns else ""

    cols_fact = ["FUF", "CONCEPTO_DE_PAGO", "PRECIO", "CANTIDAD",
                 "IMPORTE", "IVA", "TOTAL", "Periodo ECD", "Fecha Limite", "Participante"]
    df_f = df_f[[c for c in cols_fact if c in df_f.columns]]

    # ── Notas credito/debito (reliquidaciones pares: liq1 vs liq2) ───────────
    if df_reliq.empty or len(df_reliq) < 2:
        return df_f, pd.DataFrame()

    df_l1 = df_reliq.iloc[::2].reset_index(drop=True)
    df_l2 = df_reliq.iloc[1::2].reset_index(drop=True)
    min_len = min(len(df_l1), len(df_l2))
    df_l1, df_l2 = df_l1.iloc[:min_len], df_l2.iloc[:min_len]

    df_n = pd.DataFrame()
    df_n["FUF"]           = df_l2["FUF"]
    df_n["No. Ident."]    = df_l2.get("FULS", "")
    df_n["Concepto"]      = df_l2.get("CONCEPTO_DE_PAGO", "")
    df_n["Importe Orig"]  = pd.to_numeric(df_l1.get("IMPORTE", 0), errors="coerce").abs()
    df_n["Importe Mod"]   = pd.to_numeric(df_l2.get("IMPORTE", 0), errors="coerce").abs()
    df_n["Ajuste"]        = (pd.to_numeric(df_l2.get("IMPORTE", 0), errors="coerce") -
                              pd.to_numeric(df_l1.get("IMPORTE", 0), errors="coerce")).abs()
    df_n["IVA"]           = (pd.to_numeric(df_l2.get("IVA", 0), errors="coerce") -
                              pd.to_numeric(df_l1.get("IVA", 0), errors="coerce")).abs()
    df_n["TOTAL"]         = (pd.to_numeric(df_l2.get("TOTAL", 0), errors="coerce") -
                              pd.to_numeric(df_l1.get("TOTAL", 0), errors="coerce")).abs()
    df_n["Tipo"]          = (pd.to_numeric(df_l2.get("TOTAL", 0), errors="coerce") -
                              pd.to_numeric(df_l1.get("TOTAL", 0), errors="coerce")).apply(
                                  lambda x: "Debito" if x > 0 else "Credito")
    df_n["Periodo ECD"]   = _parse_periodo(df_l2["FUF"])
    df_n["Fecha Limite"]  = df_n["Periodo ECD"].apply(_next_wednesday_after_sunday)
    df_n["Participante"]  = df_l2["FUF"].str[8:15] if "FUF" in df_l2.columns else ""

    return df_f, df_n
