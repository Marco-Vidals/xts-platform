"""
ETL ERCOT — Extractores extendidos:
  - Fuel mix (generación por combustible)
  - ORDC (scarcity adder)
  - Ancillary services (precios AS DA/RT)
  - Binding constraints (shadow prices)

Todos guardan en el schema ercot.* (nueva arquitectura).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import math
import pandas as pd
from datetime import timedelta

from etl.base.db      import get_connection
from etl.ercot.ercot_api import get_token, _get_all_pages, _hour_ending_to_ts
from etl.ercot.config import AS_TYPES


def _safe(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ── Fuel Mix ─────────────────────────────────────────────────────────────────

# Mapeo columnas ERCOT → nombre normalizado fuel_type
_FUEL_MAP = {
    "coalAndLignite":       "COAL",
    "hydro":                "HYDRO",
    "nuclear":              "NUCLEAR",
    "naturalGas":           "GAS",
    "wind":                 "WIND",
    "solar":                "SOLAR",
    "powerImports":         "IMPORTS",
    "otherFuels":           "OTHER",
}


def extract_fuel_mix(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae fuel mix horario ERCOT (NP3-966-ER / gen_fuel_mix_rpt).
    Retorna DataFrame con columnas: fecha, fuel_type, gen_mw
    (formato long, una fila por hora×combustible).
    """
    token = get_token()
    df = _get_all_pages(token, "np3-966-er/gen_fuel_mix_rpt", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "size": 1000,
    })
    if df.empty:
        return pd.DataFrame(columns=["fecha", "fuel_type", "gen_mw"])

    df["fecha"] = _hour_ending_to_ts(df, "deliveryDate", "hourEnding")
    df = df.drop_duplicates(subset=["fecha"], keep="first")

    rows = []
    for _, row in df.iterrows():
        for col, fuel in _FUEL_MAP.items():
            if col in row:
                val = _safe(row[col])
                if val is not None:
                    rows.append({"fecha": row["fecha"], "fuel_type": fuel, "gen_mw": val})

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["fecha", "fuel_type", "gen_mw"])


def upsert_fuel_mix(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = upd = 0

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM ercot.fuel_mix WHERE fecha=? AND fuel_type=?",
            row["fecha"], row["fuel_type"]
        )
        if cursor.fetchone()[0]:
            # facts: solo actualizar si el valor cambia
            cursor.execute(
                "UPDATE ercot.fuel_mix SET gen_mw=? WHERE fecha=? AND fuel_type=?",
                _safe(row["gen_mw"]), row["fecha"], row["fuel_type"]
            )
            upd += 1
        else:
            cursor.execute(
                "INSERT INTO ercot.fuel_mix (fecha, fuel_type, gen_mw) VALUES (?,?,?)",
                row["fecha"], row["fuel_type"], _safe(row["gen_mw"])
            )
            ins += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[ERCOT fuel_mix] inserted={ins} updated={upd}")
    return ins, upd


# ── ORDC (scarcity adder) ─────────────────────────────────────────────────────

def extract_ordc(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae ORDC adder horario (NP6-86-CD / hb_hub_rt_prices contiene ORDC).
    Usa el endpoint np6-322-cd / ordc_sum_sched para el adder publicado.
    Retorna DataFrame con columnas: fecha, adder_rt.
    """
    token = get_token()
    # ORDC Summary Schedule: adder sumado por hora
    df = _get_all_pages(token, "np6-322-cd/ordc_sum_sched", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "size": 1000,
    })
    if df.empty:
        return pd.DataFrame(columns=["fecha", "adder_rt"])

    df["fecha"] = _hour_ending_to_ts(df, "deliveryDate", "hourEnding")
    # Columna con el ORDC adder: puede llamarse "ORDC_ADDER" o "ORDCAdder"
    adder_col = next((c for c in df.columns if "adder" in c.lower() or "ordc" in c.lower()), None)
    if adder_col is None:
        return pd.DataFrame(columns=["fecha", "adder_rt"])

    df["adder_rt"] = pd.to_numeric(df[adder_col], errors="coerce")
    df = df.drop_duplicates(subset=["fecha"], keep="first")
    return df[["fecha", "adder_rt"]].reset_index(drop=True)


def upsert_ordc(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = upd = 0

    for _, row in df.iterrows():
        cursor.execute("SELECT COUNT(*) FROM ercot.ordc WHERE fecha=?", row["fecha"])
        if cursor.fetchone()[0]:
            cursor.execute(
                "UPDATE ercot.ordc SET adder_rt=? WHERE fecha=?",
                _safe(row["adder_rt"]), row["fecha"]
            )
            upd += 1
        else:
            cursor.execute(
                "INSERT INTO ercot.ordc (fecha, adder_rt) VALUES (?,?)",
                row["fecha"], _safe(row["adder_rt"])
            )
            ins += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[ERCOT ordc] inserted={ins} updated={upd}")
    return ins, upd


# ── Ancillary Services ────────────────────────────────────────────────────────

def extract_ancillary(fecha_ini: str, fecha_fin: str, market: str = "DA") -> pd.DataFrame:
    """
    Extrae precios de AS (ancillary services) DA o RT.
    DA: np4-32-cd / dam_clrd_as
    RT: np6-86-cd / as_clrd_auc  (RT clearing)
    Retorna DataFrame: fecha, market, as_type, price, cleared_mw
    """
    token = get_token()

    if market.upper() == "DA":
        endpoint = "np4-32-cd/dam_clrd_as"
        date_param = {"deliveryDateFrom": fecha_ini, "deliveryDateTo": fecha_fin, "size": 1000}
        date_col = "deliveryDate"
        hour_col = "hourEnding"
    else:
        endpoint = "np6-86-cd/hb_hub_rt_prices"  # fallback si no hay endpoint específico RT AS
        date_param = {"deliveryDateFrom": fecha_ini, "deliveryDateTo": fecha_fin, "size": 1000}
        date_col = "deliveryDate"
        hour_col = "deliveryHour"

    df = _get_all_pages(token, endpoint, date_param)
    if df.empty:
        return pd.DataFrame(columns=["fecha", "market", "as_type", "price", "cleared_mw"])

    df["fecha"] = _hour_ending_to_ts(df, date_col, hour_col)

    rows = []
    # Las columnas de AS DA son: regUp, regDown, rrsFFR, rrsPFR, ecrsm, ecrss, nonSpin
    as_col_map = {
        "regUp":    "REGUP",
        "regDown":  "REGDN",
        "rrsFFR":   "RRSFFR",
        "rrsPFR":   "RRSPFR",
        "ecrsm":    "ECRSM",
        "ecrss":    "ECRSS",
        "nonSpin":  "NONSPIN",
        # alternativas de nombre
        "REGUP": "REGUP", "REGDN": "REGDN",
    }

    for _, row in df.iterrows():
        for col, as_type in as_col_map.items():
            if col in row and col not in [c for c in as_col_map if c == col and as_col_map[c] != col]:
                price_val = _safe(row.get(col))
                if price_val is not None:
                    rows.append({
                        "fecha":      row["fecha"],
                        "market":     market.upper(),
                        "as_type":    as_type,
                        "price":      price_val,
                        "cleared_mw": _safe(row.get(col + "Mw", row.get(col + "_mw"))),
                    })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["fecha", "market", "as_type", "price", "cleared_mw"])


def upsert_ancillary(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = upd = 0

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM ercot.ancillary WHERE fecha=? AND market=? AND as_type=?",
            row["fecha"], row["market"], row["as_type"]
        )
        if cursor.fetchone()[0]:
            cursor.execute(
                "UPDATE ercot.ancillary SET price=?, cleared_mw=? WHERE fecha=? AND market=? AND as_type=?",
                _safe(row["price"]), _safe(row["cleared_mw"]),
                row["fecha"], row["market"], row["as_type"]
            )
            upd += 1
        else:
            cursor.execute(
                "INSERT INTO ercot.ancillary (fecha,market,as_type,price,cleared_mw) VALUES (?,?,?,?,?)",
                row["fecha"], row["market"], row["as_type"],
                _safe(row["price"]), _safe(row["cleared_mw"])
            )
            ins += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[ERCOT ancillary] inserted={ins} updated={upd}")
    return ins, upd


# ── Binding Constraints ───────────────────────────────────────────────────────

def extract_binding_constraints(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae binding constraints con shadow prices (np6-86-cd / shadow_prices o similar).
    Endpoint: np6-87-cd / dam_shadow_prices
    Retorna DataFrame: fecha, constraint_name, shadow_price
    """
    token = get_token()
    df = _get_all_pages(token, "np6-87-cd/dam_shadow_prices", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "size": 1000,
    })
    if df.empty:
        return pd.DataFrame(columns=["fecha", "constraint_name", "shadow_price"])

    df["fecha"] = _hour_ending_to_ts(df, "deliveryDate", "hourEnding")

    # Detectar columnas de constraint y shadow price
    name_col  = next((c for c in df.columns if "constraint" in c.lower() or "name" in c.lower()), None)
    price_col = next((c for c in df.columns if "shadow" in c.lower() or "price" in c.lower()), None)

    if not name_col or not price_col:
        return pd.DataFrame(columns=["fecha", "constraint_name", "shadow_price"])

    result = df[["fecha"]].copy()
    result["constraint_name"] = df[name_col].astype(str)
    result["shadow_price"]    = pd.to_numeric(df[price_col], errors="coerce")
    return result.dropna(subset=["shadow_price"]).reset_index(drop=True)


def upsert_binding_constraints(df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    conn   = get_connection("XTS")
    cursor = conn.cursor()
    ins = upd = 0

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM ercot.binding_constraints WHERE fecha=? AND constraint_name=?",
            row["fecha"], row["constraint_name"]
        )
        if cursor.fetchone()[0]:
            cursor.execute(
                "UPDATE ercot.binding_constraints SET shadow_price=? WHERE fecha=? AND constraint_name=?",
                _safe(row["shadow_price"]), row["fecha"], row["constraint_name"]
            )
            upd += 1
        else:
            cursor.execute(
                "INSERT INTO ercot.binding_constraints (fecha,constraint_name,shadow_price) VALUES (?,?,?)",
                row["fecha"], row["constraint_name"], _safe(row["shadow_price"])
            )
            ins += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[ERCOT constraints] inserted={ins} updated={upd}")
    return ins, upd
