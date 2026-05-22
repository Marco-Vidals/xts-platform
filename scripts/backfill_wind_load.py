"""
Backfill Wind (West / North / South Houston) y Load ERCOT
en servidor oficina (100.70.216.12), Nov 2025 → hoy.

Ejecutar desde la carpeta raiz del proyecto:
    python scripts/backfill_wind_load.py
"""
import sys, os, pyodbc, requests, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date, timedelta
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
ERCOT_USER     = "mvidals@xiix.mx"
ERCOT_PASSWORD = ""
ERCOT_KEY      = "8908c0fc88284dfdbaed3d01955dc934"
ERCOT_CLIENT   = "fec253ea-0d06-4272-a5e6-b478baeecd70"

DB_OFFICE = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=100.70.216.12;DATABASE=XTS;"
    "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;"
)

FECHA_INI = date(2025, 11, 1)
FECHA_FIN = date.today()

# ── Token ─────────────────────────────────────────────────────────────────────
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
    print(f"  Auth status: {r.status_code}", flush=True)
    print(f"  Auth response: {r.text[:500]}", flush=True)
    js = r.json()
    tok = js.get("id_token") or js.get("access_token")
    if not tok:
        raise RuntimeError(f"Token fallido: {js}")
    return tok

# ── Fetch un día ──────────────────────────────────────────────────────────────
def fetch_day(token, endpoint, date_str, param_from, param_to, size=500):
    headers = {
        "Authorization":           f"Bearer {token}",
        "Ocp-Apim-Subscription-Key": ERCOT_KEY,
    }
    url    = f"https://api.ercot.com/api/public-reports/{endpoint}"
    params = {param_from: date_str, param_to: date_str, "size": size, "page": 1}
    rows, col_names = [], None

    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=90)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limit, esperando {wait}s…", flush=True)
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

# ── Conexión con reconexión automática ───────────────────────────────────────
def get_office_conn():
    return pyodbc.connect(DB_OFFICE)

def db_execute(sql, vals, retries=3):
    """Ejecuta un statement reconectando si la conexión se cayó."""
    for attempt in range(retries):
        try:
            conn = get_office_conn()
            cur  = conn.cursor()
            cur.execute(sql, vals)
            conn.commit()
            rowcount = cur.rowcount
            conn.close()
            return rowcount
        except pyodbc.OperationalError as e:
            if attempt < retries - 1:
                print(f"  Reconectando DB ({e})…", flush=True)
                time.sleep(3)
            else:
                raise

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    token     = get_token()
    print("Token ERCOT OK", flush=True)

    cur_date  = FECHA_INI
    day_count = 0
    total_upd = 0

    while cur_date <= FECHA_FIN:
        ds = cur_date.strftime("%Y-%m-%d")

        # ── Wind ─────────────────────────────────────────────────────────────
        df_w = fetch_day(token,
                         "np4-732-cd/wpp_hrly_avrg_actl_fcast",
                         ds, "deliveryDateFrom", "deliveryDateTo")
        wind_by_hour = {}   # hora(int) -> {"WIND_WEST": x, "WIND_NORTH": y, ...}
        if not df_w.empty:
            col_map = {c.lower(): c for c in df_w.columns}
            zone_map = {
                "stwpfloadzonewest":          "WIND_WEST",
                "stwpfloadzonenorth":         "WIND_NORTH",
                "stwpfloadzonesouthhouston":  "WIND_SOUTH_HOUSTON",
            }
            for _, row in df_w.iterrows():
                try:
                    h_raw = str(row.get("hourEnding", "0"))
                    h = int(h_raw.split(":")[0]) if ":" in h_raw else int(float(h_raw))
                except:
                    h = 0
                for lkey, dbcol in zone_map.items():
                    actual = col_map.get(lkey)
                    if actual and actual in row.index:
                        try:
                            wind_by_hour.setdefault(h, {})[dbcol] = float(row[actual])
                        except:
                            pass

        # ── Load ─────────────────────────────────────────────────────────────
        df_l = fetch_day(token,
                         "np6-345-cd/act_sys_load_by_wzn",
                         ds, "operatingDayFrom", "operatingDayTo")
        load_by_hour = {}
        if not df_l.empty and "total" in df_l.columns:
            for _, row in df_l.iterrows():
                try:
                    h_raw = str(row.get("hourEnding", "0"))
                    # hourEnding puede venir como "01:00" o como "1"
                    h = int(h_raw.split(":")[0]) if ":" in h_raw else int(float(h_raw))
                    load_by_hour[h] = float(row["total"])
                except:
                    pass

        # ── UPDATE DB hora a hora ─────────────────────────────────────────────
        from datetime import datetime as _dt
        day_upd = 0
        for h in range(1, 25):
            # hourEnding 24 = medianoche = 00:00:00 del día siguiente
            if h == 24:
                fecha = _dt(cur_date.year, cur_date.month, cur_date.day) + timedelta(days=1)
            else:
                fecha = _dt(cur_date.year, cur_date.month, cur_date.day, h, 0, 0)
            wd    = wind_by_hour.get(h, {})
            ld    = load_by_hour.get(h)

            sets, vals = [], []
            for dbcol, val in [
                ("WIND_WEST",          wd.get("WIND_WEST")),
                ("WIND_NORTH",         wd.get("WIND_NORTH")),
                ("WIND_SOUTH_HOUSTON", wd.get("WIND_SOUTH_HOUSTON")),
                ("LOAD_ERCOT_MW",      ld),
            ]:
                if val is not None:
                    sets.append(f"{dbcol}=?")
                    vals.append(val)

            if sets:
                # Intentar UPDATE primero; si no existe la fila, INSERT
                update_vals = vals + [fecha]
                rc = db_execute(
                    f"UPDATE dbo.DATOS_ERCOT SET {','.join(sets)} WHERE fecha=?",
                    update_vals,
                )
                if rc == 0:
                    insert_cols = ["fecha"] + [s.split("=")[0] for s in sets]
                    insert_vals = [fecha] + vals
                    db_execute(
                        f"INSERT INTO dbo.DATOS_ERCOT ({','.join(insert_cols)}) VALUES ({','.join(['?']*len(insert_cols))})",
                        insert_vals,
                    )
                day_upd += 1

        total_upd += day_upd
        day_count += 1
        print(f"{ds}  wind_horas={len(wind_by_hour)}  load_horas={len(load_by_hour)}  upd={day_upd}  total={total_upd}", flush=True)

        # Renovar token cada 7 días
        if day_count % 7 == 0:
            try:
                token = get_token()
                print("  Token renovado", flush=True)
            except Exception as e:
                print(f"  Warning: no se pudo renovar token: {e}", flush=True)

        time.sleep(0.5)
        cur_date += timedelta(days=1)

    print(f"\nBACKFILL COMPLETO — {day_count} días, {total_upd} filas actualizadas")


if __name__ == "__main__":
    main()
