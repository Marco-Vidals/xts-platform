# -*- coding: utf-8 -*-

"""
Created on Thu Jul 27 12:23:15 2023

@author: Yisus craist
"""

import zipfile
import datetime
import csv
import io
import base64
from zeep import Client
import zipfile36 as zipfile
import shutil
import os
from datetime import timedelta
import time
from dotenv import load_dotenv

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_SCRIPT_DIR, "..", "Extractors", ".env"))
BASE_FAC = os.environ.get(
    "FACTURACION_BASE",
    os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "Facturacion"))
)


def remove_strings_with_endings(input_list, endings_to_remove):
    output_list = [s for s in input_list if not any(s.endswith(ending) for ending in endings_to_remove)]
    return output_list


def descargar_sistema(listafechas, sistema, sc, users, pssw, remover):
    """Descarga los EDCs de un sistema (BCA o SIN) para el rango de fechas dado."""
    MAX_INTENTOS = 3
    ESPERA_SEGUNDOS = 10
    ECUENTA_DROP = os.path.join(BASE_FAC, "Ecuenta Drop")
    os.makedirs(ECUENTA_DROP, exist_ok=True)
    url = "https://ws01.cenace.gob.mx:8081/WSDownLoadEdoCta/EdoCuentaService.svc?singleWsdl"

    missing_files = []

    for dia in listafechas:
        year  = str(dia.year)
        month = str(dia.month).zfill(2)
        day   = str(dia.day).zfill(2)

        title_list = [f"EC{year}{month}{day}{sistema}-M024{s}" for s in sc]
        print(f"\n[{sistema}] Descargando {dia.strftime('%Y-%m-%d')} — esperados: {title_list}")

        client = Client(wsdl=url)
        names = []
        descarga_exitosa = False

        for intento in range(1, MAX_INTENTOS + 1):
            try:
                print(f"  Intento {intento}/{MAX_INTENTOS}...")
                archivo = client.service.GetEstadoCuentas(users, pssw, dia, sistema, "M024", None, "C")
                names = []
                for edc in archivo.EC.EdoCuenta:
                    decoded_content = base64.b64decode(base64.b64encode(edc.File_C))
                    with zipfile.ZipFile(io.BytesIO(decoded_content)) as zip_file:
                        # Usar namelist() para obtener el nombre real del archivo dentro del ZIP
                        zip_names = [n for n in zip_file.namelist() if n.endswith('.csv')]
                        if not zip_names:
                            raise ValueError(f"No se encontró ningún CSV dentro del ZIP de {edc.Subcuenta}")
                        name = zip_names[0]
                        names.append(name)
                        csv_file = zip_file.extract(name, ECUENTA_DROP)
                        print(f"  Extraído: {csv_file}")
                descarga_exitosa = True
                break
            except Exception as e:
                print(f"  Error en intento {intento}: {e}")
                if intento < MAX_INTENTOS:
                    print(f"  Esperando {ESPERA_SEGUNDOS} segundos antes de reintentar...")
                    time.sleep(ESPERA_SEGUNDOS)
                else:
                    print(f"  Fallaron los {MAX_INTENTOS} intentos para {dia.strftime('%Y-%m-%d')} [{sistema}] — continuando con los demás días.")

        if not descarga_exitosa:
            missing_files.extend(title_list)
            continue

        # Renombrar archivos al formato corto (20 chars + .csv)
        for name in names:
            source      = os.path.join(ECUENTA_DROP, name)
            destination = os.path.join(ECUENTA_DROP, name[0:21] + '.csv')
            if os.path.exists(source):
                shutil.move(source, destination)

        # Verificar cuáles archivos llegaron
        print(f"\n  Verificando archivos de {dia.strftime('%Y-%m-%d')} [{sistema}]...")
        for title in title_list:
            file_path = os.path.join(ECUENTA_DROP, f'{title}.csv')
            if os.path.exists(file_path):
                print(f"  OK: {title}.csv")
            else:
                missing_files.append(title)
                print(f"  FALTA: {title}.csv")

        # Eliminar EDCs que no se usan (EEP, IEP en SIN)
        if sistema == 'SIN':
            for r in remover:
                file_path = os.path.join(ECUENTA_DROP, f"EC{year}{month}{day}SIN-M024{r}.csv")
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"  Eliminado (no requerido): EC{year}{month}{day}SIN-M024{r}.csv")

    return missing_files


# ── Credenciales (desde .env) ─────────────────────────────────────────────────
users_bca = os.environ.get("CENACE_ECD_USER_BCA", "")
pssw_bca  = os.environ.get("CENACE_ECD_PASS_BCA", "")
users_sin = os.environ.get("CENACE_ECD_USER_SIN", "")
pssw_sin  = os.environ.get("CENACE_ECD_PASS_SIN", "")
if not all([users_bca, pssw_bca, users_sin, pssw_sin]):
    raise SystemExit("ERROR: Faltan credenciales CENACE_ECD_* en el archivo .env")

# ── Rango de fechas (semana de operación: lunes a domingo, 2 semanas atrás) ──
# Ejemplo: si hoy es lunes 6 de abril → descarga del 23 al 29 de marzo
hoy   = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
end   = hoy - timedelta(days=8)   # domingo de hace 2 semanas
start = end - timedelta(days=6)   # lunes de hace 2 semanas

listafechas = []
fecha = start
while fecha <= end:
    listafechas.append(fecha)
    fecha += timedelta(days=1)

print(f"\nRango: {start.strftime('%Y-%m-%d')} al {end.strftime('%Y-%m-%d')} ({len(listafechas)} días)")

remover = ['EEP', 'IEP']  # EDCs que no se necesitan del SIN

# ── Descarga ──────────────────────────────────────────────────────────────────
sc_bca = ['ERO', 'ITJ', 'ETJ', 'IRO']
sc_sin = ['EEP', 'ERD', 'ILA', 'EGT', 'IEP', 'IRD', 'ELA', 'IGT', 'TBF']

print("\n" + "="*60)
print("DESCARGANDO BCA")
print("="*60)
missing_bca = descargar_sistema(listafechas, 'BCA', sc_bca, users_bca, pssw_bca, remover)

print("\n" + "="*60)
print("DESCARGANDO SIN")
print("="*60)
missing_sin = descargar_sistema(listafechas, 'SIN', sc_sin, users_sin, pssw_sin, remover)

# ── Resumen final ─────────────────────────────────────────────────────────────
missing_all = missing_bca + missing_sin
missing_all = remove_strings_with_endings(missing_all, remover)

print("\n" + "="*60)
if len(missing_all) == 0:
    print("✓ Todos los archivos descargados correctamente.")
else:
    print(f"ARCHIVOS FALTANTES ({len(missing_all)}):")
    for f in missing_all:
        print(f"  - {f}")
print("="*60)
