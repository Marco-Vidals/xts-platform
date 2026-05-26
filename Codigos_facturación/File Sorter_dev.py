# -*- coding: utf-8 -*-
"""
Created on Thu Jul 20 14:34:48 2023

@author: xiixt
"""

import os
import shutil
from dotenv import load_dotenv

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_SCRIPT_DIR, "..", "Extractors", ".env"))
BASE_FAC = os.environ.get(
    "FACTURACION_BASE",
    os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "Facturacion"))
)

folder_path = os.path.join(BASE_FAC, "Ecuenta Drop")




# Get a list of all the files in the folder
file_list = os.listdir(folder_path)

# Iterate over each file
for file_name in file_list:
    # Solo procesar archivos CSV con el formato esperado (ECyyyymmdd...)
    if not file_name.endswith('.csv') or not file_name.startswith('EC') or len(file_name) < 10:
        continue

    # Extract the date components from the file name
    date_str = file_name[2:10]
    try:
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
    except ValueError:
        print(f"Archivo con formato inesperado, se omite: {file_name}")
        continue

    # Generate the destination folder path based on the date components
    destination_path = BASE_FAC

    destination_folder = os.path.join(destination_path, str(year), f"{month:02d}", f"{day:02d}")

    # Crear la carpeta destino si no existe
    os.makedirs(destination_folder, exist_ok=True)

    # Move the file to the destination folder
    source_file = os.path.join(folder_path, file_name)
    destination_file = os.path.join(destination_folder, file_name)
    shutil.move(source_file, destination_file)

print("Files sorted successfully.")