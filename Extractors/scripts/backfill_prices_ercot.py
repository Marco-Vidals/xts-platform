"""
Backfill DA_DCL, DA_DCR, RT_DCL, RT_DCR, SOLAR_ERCOT en DATOS_ERCOT
Rango: 2024-07-05 -> hoy

Ejecutar desde la carpeta raiz:
    python scripts/backfill_prices_ercot.py
"""
import sys, os, pyodbc, requests, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date, timedelta, datetime
import pandas as pd

# ── Config ─────────────────────────────────────────────────────────────────────
ERCOT_USER     = "mvidals@xiix.mx"
ERCOT_PASSWORD = ""
ERCOT_KEY      = "8908c0fc88284dfdbaed3d01955dc934"
ERCOT_CLIENT   = "fec253ea-0d06-4272-a5e6-b478baeecd70"

DB_OFFICE = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=100.70.216.12;DATABASE=XTS;"
    "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;"
)

FECHA_INI = date(2024, 7, 5)
FECHA_FIN = date.today()

# ── Token ──────────────────────────────────────────────────────────────────────
def get_token():
    r = requests.post(
        "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/"
        "B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token",
        data={
            "grant_type":    "password",
            "username":      ERCOT_USER,
            "password":      ERCOT_PASSWORD,
            "response_type": "id_token",
            "scope":         f"openid {ERCOT_CLIENT} offline_access",
            "client_id":     ERCOT_CLIENT,
        }, timeout=30,
    )
    js = r.json()
    tok = js.get("id_token") or js.get("access_token")
    if not tok:
        raise RuntimeError(f"Token fallido: {js}")
    return tok

# ── Fetch un dia ───────────────────────────────────────────────────────────────
def fetch_day(token, endpoint, date_str, extra_params=None, size=1000):
    headers = {
        "Authorization":             f"Bearer {token}",
        "Ocp-Apim-Subscription-Key": ERCOT_KEY,
    }
    url    = f"https://api.ercot.com/api/public-reports/{endpoint}"
    params = {"deliveryDateFrom": date_str, "deliveryDateTo": date_str,
              "size": size, "page": 1}
    if extra_params:
        params.update(extra_params)

    rows, col_names = [], None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=90)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limit, esperando {wait}s...", flush=True)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                print(f"  HTTP {r.status_code} para {endpoint} {date_str}", flush=True)
                return pd.DataFrame()
            js = r.json()
            if col_names is None:
                fields = js.get("fields", [])
                if fields and isinstance(fields[0], dict):
                    col_names = [f["name"] for f in fields]
            rows.extend(js.get("data", []))
            total_pages = js.get("_meta", {}).get("totalPages", 1)
            for pg in range(2, total_pages + 1):
                params["page"] = pg
                r2 = requests.get(url, headers=headers, params=params, timeout=90)
                if r2.status_code == 200:
                    rows.extend(r2.json().get("data", []))
            break
        except Exception as ex:
            print(f"  Intento {attempt+1} fallido: {ex}", flush=True)
            time.sleep(15)

    if not rows:
        return pd.DataFrame()
    if col_names and isinstance(rows[0], list):
        return pd.DataFrame(rows, columns=col_names)
    return pd.DataFrame(rows)

# ── Parsear hourEnding → int 1-24 ─────────────────────────────────────────────
def parse_hour(val):
    s = str(val)
    try:
        return int(s.split(":")[0]) if ":" in s else int(float(s))
    except:
        return 0

# ── DA prices para un dia/nodo → dict {hora: precio} ──────────────────────────
def da_prices_day(token, date_str, node):
    df = fetch_day(token, "np4-190-cd/dam_stlmnt_pnt_prices",
                   date_str, {"settlementPoint": node})
    if df.empty:
        return {}
    price_col = next((c for c in df.columns if "settlementpointprice" in c.lower()), None)
    hour_col  = next((c for c in df.columns if "hourending" in c.lower()), None)
    if not price_col or not hour_col:
        return {}
    result = {}
    for _, row in df.iterrows():
        h = parse_hour(row[hour_col])
        try:
            result[h] = float(row[price_col])
        except:
            pass
    return result

# ── Solar para un dia → dict {hora: solar_mw} ────────────────────────────────
def solar_day(token, date_str):
    df = fetch_day(token, "np4-745-cd/spp_hrly_actual_fcast_geo", date_str)
    if df.empty:
        return {}
    hour_col = next((c for c in df.columns if "hourending" in c.lower()), None)
    mw_col   = next((c for c in df.columns if "gensystemwide" in c.lower()), None)
    if not hour_col or not mw_col:
        return {}
    # tomar el valor mas reciente por hora (postedDatetime DESC)
    posted_col = next((c for c in df.columns if "posteddatetime" in c.lower()), None)
    if posted_col:
        df = df.sort_values(posted_col, ascending=False)
    result = {}
    for _, row in df.iterrows():
        h = parse_hour(row[hour_col])
        if h not in result:
            try:
                result[h] = float(row[mw_col])
            except:
                pass
    return result

# ── RT prices para un dia/nodo → dict {hora: precio_promedio} ─────────────────
def rt_prices_day(token, date_str, node):
    df = fetch_day(token, "np6-905-cd/spp_node_zone_hub",
                   date_str, {"settlementPoint": node}, size=2000)
    if df.empty:
        return {}
    price_col = next((c for c in df.columns if "settlementpointprice" in c.lower()), None)
    # RT usa deliveryHour + deliveryInterval (15 min)
    hour_col  = next((c for c in df.columns
                      if c.lower() in ("deliveryhour", "hourending")), None)
    if not price_col or not hour_col:
        return {}
    # Agrupar por hora y promediar los intervalos de 15 min
    accum = {}  # hora -> [precios]
    for _, row in df.iterrows():
        h = parse_hour(row[hour_col])
        try:
            accum.setdefault(h, []).append(float(row[price_col]))
        except:
            pass
    return {h: sum(v) / len(v) for h, v in accum.items() if v}

# ── DB con reconexion ──────────────────────────────────────────────────────────
def db_execute(sql, vals, retries=3):
    for attempt in range(retries):
        try:
            conn = pyodbc.connect(DB_OFFICE)
            cur  = conn.cursor()
            cur.execute(sql, vals)
            conn.commit()
            rc = cur.rowcount
            conn.close()
            return rc
        except pyodbc.OperationalError as e:
            if attempt < retries - 1:
                print(f"  Reconectando DB ({e})...", flush=True)
                time.sleep(3)
            else:
                raise

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    token     = get_token()
    print(f"Token OK  |  Rango: {FECHA_INI} -> {FECHA_FIN}", flush=True)

    cur_date  = FECHA_INI
    day_count = 0
    total_upd = 0

    while cur_date <= FECHA_FIN:
        ds = cur_date.strftime("%Y-%m-%d")

        da_dcl  = da_prices_day(token, ds, "DC_L")
        da_dcr  = da_prices_day(token, ds, "DC_R")
        rt_dcl  = rt_prices_day(token, ds, "DC_L")
        rt_dcr  = rt_prices_day(token, ds, "DC_R")
        solar   = solar_day(token, ds)

        day_upd = 0
        for h in range(1, 25):
            if h == 24:
                fecha = datetime(cur_date.year, cur_date.month, cur_date.day) + timedelta(days=1)
            else:
                fecha = datetime(cur_date.year, cur_date.month, cur_date.day, h, 0, 0)

            sets, vals = [], []
            for dbcol, src in [
                ("DA_DCL",      da_dcl.get(h)),
                ("DA_DCR",      da_dcr.get(h)),
                ("RT_DCL",      rt_dcl.get(h)),
                ("RT_DCR",      rt_dcr.get(h)),
                ("SOLAR_ERCOT", solar.get(h)),
            ]:
                if src is not None:
                    sets.append(f"{dbcol}=?")
                    vals.append(src)

            if not sets:
                continue

            update_vals = vals + [fecha]
            rc = db_execute(
                f"UPDATE dbo.DATOS_ERCOT SET {','.join(sets)} WHERE fecha=?",
                update_vals,
            )
            if rc == 0:
                insert_cols = ["fecha"] + [s.split("=")[0] for s in sets]
                insert_vals = [fecha] + vals
                db_execute(
                    f"INSERT INTO dbo.DATOS_ERCOT ({','.join(insert_cols)}) "
                    f"VALUES ({','.join(['?']*len(insert_cols))})",
                    insert_vals,
                )
            day_upd += 1

        total_upd += day_upd
        day_count += 1
        print(
            f"{ds}  DA_DCL={len(da_dcl)}h  DA_DCR={len(da_dcr)}h  "
            f"RT_DCL={len(rt_dcl)}h  RT_DCR={len(rt_dcr)}h  "
            f"SOLAR={len(solar)}h  upd={day_upd}  total={total_upd}",
            flush=True,
        )

        # Renovar token cada 7 dias
        if day_count % 7 == 0:
            try:
                token = get_token()
                print("  Token renovado", flush=True)
            except Exception as e:
                print(f"  Warning: no se pudo renovar token: {e}", flush=True)

        time.sleep(0.5)
        cur_date += timedelta(days=1)

    print(f"\nBACKFILL COMPLETO -- {day_count} dias, {total_upd} filas actualizadas")


if __name__ == "__main__":
    main()
