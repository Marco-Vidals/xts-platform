# -*- coding: utf-8 -*-
"""
run_weekly.py
Corre el flujo completo de facturación semanal en orden.
Ejecutar cada lunes: python run_weekly.py
"""

import subprocess
import sys
import os
import argparse

BASE = os.path.dirname(os.path.abspath(__file__))

PASOS = [
    ("1. Descarga de EDCs",              "ecuentadrop 2 1.py"),
    ("2. Organizar archivos por fecha",  "File Sorter_dev.py"),
    ("3. Extraer datos de EDCs",         "File reader 2.7_dev.py"),
    ("4. Generar facturas",              "facturas.py"),
    ("5. Generar notas de crédito/débito", "notas.py"),
]

parser = argparse.ArgumentParser()
parser.add_argument("--desde", type=int, default=None)
parser.add_argument("--hasta", type=int, default=len(PASOS))
args, _ = parser.parse_known_args()

print("=" * 60)
print("   FLUJO DE FACTURACIÓN SEMANAL — XTS")
print("=" * 60)
print("\nPasos disponibles:")
for idx, (nombre, _) in enumerate(PASOS, 1):
    print(f"  {idx}. {nombre}")

if args.desde is not None:
    paso_inicio = args.desde
else:
    desde = input("\n¿Desde qué paso quieres empezar? (Enter para empezar desde el 1): ").strip()
    paso_inicio = int(desde) if desde.isdigit() and 1 <= int(desde) <= len(PASOS) else 1

paso_fin = args.hasta
print(f"\nEmpezando desde el paso {paso_inicio} hasta el paso {paso_fin}...\n")

for nombre, archivo in PASOS[paso_inicio - 1: paso_fin]:
    script = os.path.join(BASE, archivo)
    print(f"\n{'─' * 60}")
    print(f"PASO {nombre}")
    print(f"{'─' * 60}")

    resultado = subprocess.run([sys.executable, script])

    if resultado.returncode != 0:
        print(f"\n❌  Falló: {nombre}")
        print("    El proceso se detuvo. Corrige el error antes de continuar.")
        sys.exit(1)

    print(f"\n✓  {nombre} completado.")

print(f"\n{'=' * 60}")
print("✓  Facturación semanal completada exitosamente.")
print("=" * 60)
