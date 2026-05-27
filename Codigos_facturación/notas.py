import pandas as pd
import requests
import datetime
from datetime import timedelta
import numpy as np
import json
import os
import argparse
from dotenv import load_dotenv

_parser = argparse.ArgumentParser()
_parser.add_argument("--folio", type=int, default=None)
_parser.add_argument("--include-fufs", type=str, default=None,
                     help="Comma-separated FUFs to process (default: all)")
_parser.add_argument("--auto-confirm", action="store_true",
                     help="Skip y/n confirmation for each document")
_args, _ = _parser.parse_known_args()

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_SCRIPT_DIR, "..", "Extractors", ".env"))
BASE_FAC = os.environ.get("FACTURACION_BASE") or os.path.normpath(
    os.path.join(_SCRIPT_DIR, "..", "..", "Facturacion")
)

f = pd.read_excel(os.path.join(BASE_FAC, 'XiiXNotas.xlsx'))
f.replace("", 0)
f.fillna(0, inplace=True)

if _args.include_fufs:
    _include = set(x.strip() for x in _args.include_fufs.split(","))
    f = f[f["FUF"].astype(str).isin(_include)].reset_index(drop=True)

_folios_path = os.path.join(BASE_FAC, 'folios_timbrados.csv')
if os.path.exists(_folios_path):
    _folios_df = pd.read_csv(_folios_path)
    _folios_map = dict(zip(_folios_df['FUF'].astype(str), _folios_df['UUID'].astype(str)))
    _llenados = 0
    for _idx in f.index:
        _fuf = str(f.at[_idx, 'FUF'])
        if _fuf in _folios_map and _folios_map[_fuf] not in ('', '0', 'nan'):
            f.at[_idx, 'Folio Fiscal'] = _folios_map[_fuf]
            _llenados += 1
    print(f"✓ Folios Fiscales cargados automáticamente: {_llenados}/{len(f)} notas")
else:
    print("⚠️  folios_timbrados.csv no encontrado — verifica que facturas.py ya corrió")

id_duplicados = f[f.duplicated(subset='FUF', keep=False)]
id_unicos = f.drop_duplicates(subset='FUF', keep=False)
grupo=id_duplicados.groupby('FUF')

# Guarda los resultados en archivos separados
id_duplicados.to_excel('id_duplicados.xlsx', index=False)
id_unicos.to_excel('id_unicos.xlsx', index=False)

if _args.folio is not None:
    folio = _args.folio - 1
else:
    folio = int(input("Ingresa el número de folio:")) - 1
a = folio + 1  # valor por defecto si no hay únicos

if len(id_unicos)>0:
    import notas1
    f=pd.read_excel('id_unicos.xlsx')
    a=notas1.notas(len(id_unicos), f, folio, auto_confirm=_args.auto_confirm)

folio=a - 1

def encontrar_renglon(archivo, cadena):
    df = pd.read_excel(archivo)
    for indice, fila in df.iterrows():
        if cadena in fila.values:
            print(f"La cadena '{cadena}' se encuentra en la fila {indice}.")
            return indice

if len(grupo)>0:
    for i in grupo:
        f=pd.read_excel('id_duplicados.xlsx')
        folio=folio + 1
        cadena=i[0]
        renglon=encontrar_renglon('id_duplicados.xlsx', i[0])

        if len(i[1])==2:
            import notas2
            f1=i[1]
            notas2.notas(renglon, f, folio, auto_confirm=_args.auto_confirm)
        if len(i[1])==3:
            f1=i[1]
            import notas3
            notas3.notas(renglon, f, folio, auto_confirm=_args.auto_confirm)
        if len(i[1])==4:
            f1=i[1]
            import notas4
            notas4.notas(renglon, f, folio, auto_confirm=_args.auto_confirm)

