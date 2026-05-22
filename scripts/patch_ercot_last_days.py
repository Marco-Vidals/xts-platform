"""
Patch ERCOT faltante: 2026-04-03 -> hoy
El backfill principal crasho en NaN; este script cubre los dias restantes.
"""
import sys, os, pyodbc, requests, time, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date, timedelta, datetime
import pandas as pd

ERCOT_USER     = "mvidals@xiix.mx"
ERCOT_PASSWORD = ""
ERCOT_KEY      = "8908c0fc88284dfdbaed3d01955dc934"
ERCOT_CLIENT   = "fec253ea-0d06-4272-a5e6-b478baeecd70"

DB_OFFICE = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=100.70.216.12;DATABASE=XTS;"
    "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;"
)

FECHA_INI = date(2026, 4, 3)
FECHA_FIN = date.today()

# -- Importar helpers del backfill principal
from scripts.backfill_prices_ercot import (
    get_token, da_prices_day, rt_prices_day, solar_day,
    db_execute, parse_hour
)

def main():
    token = get_token()
    print(f"Token OK  |  Patch: {FECHA_INI} -> {FECHA_FIN}", flush=True)

    cur_date  = FECHA_INI
    total_upd = 0

    while cur_date <= FECHA_FIN:
        ds = cur_date.strftime("%Y-%m-%d")

        da_dcl = da_prices_day(token, ds, "DC_L")
        da_dcr = da_prices_day(token, ds, "DC_R")
        rt_dcl = rt_prices_day(token, ds, "DC_L")
        rt_dcr = rt_prices_day(token, ds, "DC_R")
        solar  = solar_day(token, ds)

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
                if src is not None and not (isinstance(src, float) and math.isnan(src)):
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
        da_h = len(da_dcl); da_r = len(da_dcr)
        rt_h = len(rt_dcl); rt_r = len(rt_dcr)
        sol  = len(solar)
        print(f"{ds}  DA_DCL={da_h}h  DA_DCR={da_r}h  RT_DCL={rt_h}h  RT_DCR={rt_r}h  SOLAR={sol}h  upd={day_upd}  total={total_upd}", flush=True)

        cur_date += timedelta(days=1)
        time.sleep(1)

    print(f"\nPatch ERCOT completo — {total_upd} filas procesadas.", flush=True)

if __name__ == "__main__":
    main()
