"""
Exporta DA y RT de ERCOT (DC_L, DC_R) a Excel.
Uso: python scripts/export_ercot_da_rt.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from datetime import date

DB = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=100.70.216.12;DATABASE=XTS;"
    "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;"
)

FECHA_INI = date(2026, 3, 14)
FECHA_FIN = date(2026, 3, 17)
OUT = os.path.join(os.path.dirname(__file__), "..", "ERCOT_DA_RT_14_17mar2026.xlsx")

import pyodbc
conn = pyodbc.connect(DB)
df = pd.read_sql(
    """
    SELECT fecha, DA_DCL, DA_DCR, RT_DCL, RT_DCR
    FROM dbo.DATOS_ERCOT
    WHERE CAST(fecha AS DATE) BETWEEN ? AND ?
    ORDER BY fecha
    """,
    conn, params=[FECHA_INI, FECHA_FIN],
)
conn.close()

df["fecha"] = pd.to_datetime(df["fecha"])
df["Fecha"] = df["fecha"].dt.strftime("%Y-%m-%d")
df["Hora"]  = df["fecha"].dt.strftime("%H:00")

out = df[["Fecha", "Hora", "DA_DCL", "DA_DCR", "RT_DCL", "RT_DCR"]].copy()
out.columns = ["Fecha", "Hora", "DA DC_L ($/MWh)", "DA DC_R ($/MWh)", "RT DC_L ($/MWh)", "RT DC_R ($/MWh)"]

out.to_excel(OUT, index=False, sheet_name="ERCOT DA RT")
print(f"Exportado: {OUT}  ({len(out)} filas)")
