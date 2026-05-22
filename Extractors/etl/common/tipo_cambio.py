"""
ETL Tipo de Cambio — USD/MXN FIX (Banco de México).

Fuente primaria : API SIE Banxico (serie SF43718)
                  Requiere token gratuito en:
                  https://www.banxico.org.mx/SieAPIRest/service/v1/token
                  Configurar en variable de entorno BANXICO_TOKEN.

Fuente de respaldo: Frankfurter API (tasa de mercado, sin registro)

Tabla destino: XTS.dbo.Tipo_Cambio  (una fila por fecha)
"""
import os
import sys
import requests
import pandas as pd
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from etl.common.db_connection import get_connection

BANXICO_TOKEN  = os.environ.get("BANXICO_TOKEN", "")
BANXICO_SERIES = "SF43718"   # Tipo de cambio FIX USD/MXN
BANXICO_BASE   = "https://www.banxico.org.mx/SieAPIRest/service/v1"
FRANKFURTER    = "https://api.frankfurter.app"
FAWAZ_CDN      = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/usd.json"


# ── Banxico SIE ───────────────────────────────────────────────────────────────
def _banxico(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Consulta la API SIE de Banxico.
    Requiere BANXICO_TOKEN en el ambiente.
    """
    if not BANXICO_TOKEN:
        raise ValueError("BANXICO_TOKEN no configurado")

    url = f"{BANXICO_BASE}/series/{BANXICO_SERIES}/datos/{fecha_ini}/{fecha_fin}"
    headers = {"Bmx-Token": BANXICO_TOKEN}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    datos = resp.json()["bmx"]["series"][0]["datos"]
    df = pd.DataFrame(datos)
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True)
    df["TC"]    = pd.to_numeric(df["dato"], errors="coerce")
    return df[["fecha", "TC"]].dropna()


# ── Frankfurter (respaldo 1) ──────────────────────────────────────────────────
def _frankfurter(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """Tasa de mercado USD/MXN de Frankfurter (ECB data)."""
    url = f"{FRANKFURTER}/{fecha_ini}..{fecha_fin}"
    resp = requests.get(url, params={"from": "USD", "to": "MXN"}, timeout=30)
    resp.raise_for_status()
    js = resp.json()
    rates = js.get("rates", {})
    rows = [{"fecha": pd.Timestamp(d), "TC": v["MXN"]} for d, v in rates.items()]
    return pd.DataFrame(rows).sort_values("fecha").reset_index(drop=True)


# ── Fawazahmed CDN (respaldo 2, fecha por fecha) ──────────────────────────────
def _fawaz_range(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Descarga TC de cdn.jsdelivr.net/@fawazahmed0/currency-api.
    Hace una peticion por dia (mismo CDN que usa APP_Claude.py para live TC).
    """
    ini = date.fromisoformat(fecha_ini)
    fin = date.fromisoformat(fecha_fin)
    rows = []
    d = ini
    while d <= fin:
        try:
            url = FAWAZ_CDN.format(date=d.isoformat())
            resp = requests.get(url, timeout=15, verify=False)
            if resp.ok:
                mxn = resp.json().get("usd", {}).get("mxn")
                if mxn:
                    rows.append({"fecha": pd.Timestamp(d), "TC": float(mxn)})
        except Exception:
            pass
        d += timedelta(days=1)
    return pd.DataFrame(rows)


# ── Extracción principal ──────────────────────────────────────────────────────
def extract_tipo_cambio(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Obtiene el tipo de cambio USD/MXN para el rango dado.
    Orden: Banxico -> Frankfurter -> Fawazahmed CDN.
    """
    try:
        print("[TC] Consultando Banxico SIE...")
        df = _banxico(fecha_ini, fecha_fin)
        if not df.empty:
            print(f"[TC] Banxico OK - {len(df)} registros")
            return df
    except Exception as e:
        print(f"[TC] Banxico fallo ({e})")

    try:
        print("[TC] Intentando Frankfurter...")
        df = _frankfurter(fecha_ini, fecha_fin)
        if not df.empty:
            print(f"[TC] Frankfurter OK - {len(df)} registros")
            return df
    except Exception as e:
        print(f"[TC] Frankfurter fallo ({e})")

    print("[TC] Usando Fawazahmed CDN (fecha por fecha)...")
    df = _fawaz_range(fecha_ini, fecha_fin)
    print(f"[TC] Fawazahmed OK - {len(df)} registros")
    return df


# ── Upsert ────────────────────────────────────────────────────────────────────
def upsert_tipo_cambio(df: pd.DataFrame) -> None:
    """Inserta o actualiza en XTS.dbo.Tipo_Cambio."""
    if df.empty:
        print("[TC] Sin datos.")
        return

    conn   = get_connection("XTS")
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM TIPO_CAMBIO WHERE fecha = ?", row["fecha"])
        existe = cursor.fetchone()[0]

        if existe:
            cursor.execute(
                "UPDATE TIPO_CAMBIO SET TC = ? WHERE fecha = ?",
                row["TC"], row["fecha"])
        else:
            cursor.execute(
                "INSERT INTO TIPO_CAMBIO (fecha, TC) VALUES (?, ?)",
                row["fecha"], row["TC"])

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[TC] {len(df)} registros guardados en TIPO_CAMBIO.")


# ── CLI rápido ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ETL Tipo de Cambio USD/MXN")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--desde",   type=str)
    parser.add_argument("--hasta",   type=str)
    args = parser.parse_args()

    if args.backfill and args.desde and args.hasta:
        fi, ff = args.desde, args.hasta
    else:
        ayer = date.today() - timedelta(days=1)
        fi = ff = ayer.strftime("%Y-%m-%d")

    df = extract_tipo_cambio(fi, ff)
    print(df.tail(5).to_string(index=False))
    upsert_tipo_cambio(df)
