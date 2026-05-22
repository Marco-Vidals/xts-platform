"""
ETL — Descarga Estados de Cuenta CENACE (ECD) via SOAP API.
Adaptado de ecuentadrop.py para uso en produccion.

Uso:
    from etl.cenace.ecd_extractor import download_ecd
    download_ecd(date(2026,3,14), date(2026,3,16), "BCA")
    download_ecd(date(2026,3,14), date(2026,3,16), "SIN")
"""
import io, os, base64, shutil, zipfile, time
from datetime import date, datetime, timedelta

# Ruta base donde se guardan los ECDs (organizada por año/mes/dia)
ECD_BASE = os.path.join(
    os.path.expanduser("~"),
    "OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV",
    "XTS R&D", "Facturacion",
)

# Credenciales CENACE
_CREDS = {"BCA": "EnriqueXTSBCA", "SIN": "EnriqueXTSSIN"}
_PSSW  = "XTSENPV1"
_WSDL  = "https://ws01.cenace.gob.mx:8081/WSDownLoadEdoCta/EdoCuentaService.svc?singleWsdl"

# Subcuentas que se descargan por sistema
_SUBCUENTAS = {
    "BCA": ["ERO", "ITJ", "ETJ", "IRO"],
    "SIN": ["ERD", "ELA", "EGT", "IGT"],   # solo las que interesan (sin EEP, ILA, etc.)
}


def _fecha_dir(d: date) -> str:
    """Carpeta destino para un dia dado."""
    return os.path.join(ECD_BASE, d.strftime("%Y"), d.strftime("%m"), d.strftime("%d"))


def _expected_files(d: date, sistema: str) -> list[str]:
    """Lista de rutas esperadas para un dia y sistema."""
    year  = d.strftime("%Y")
    month = d.strftime("%m")
    day   = d.strftime("%d")
    return [
        os.path.join(_fecha_dir(d), f"EC{year}{month}{day}{sistema}-M024{sc}.csv")
        for sc in _SUBCUENTAS[sistema]
    ]


def already_downloaded(d: date, sistema: str) -> bool:
    """True si todos los archivos esperados ya existen."""
    return all(os.path.exists(f) for f in _expected_files(d, sistema))


def download_ecd(fecha_ini: date, fecha_fin: date, sistema: str,
                 skip_existing: bool = True) -> dict:
    """
    Descarga ECDs del CENACE SOAP API para el rango dado.

    Returns:
        dict con keys:
          'ok'      -> list[date] fechas descargadas exitosamente
          'skipped' -> list[date] ya existian
          'error'   -> list[date] fallaron
    """
    from zeep import Client as ZeepClient

    resultado = {"ok": [], "skipped": [], "error": []}
    user = _CREDS[sistema]

    cur = fecha_ini
    while cur <= fecha_fin:
        if skip_existing and already_downloaded(cur, sistema):
            print(f"[ECD] {cur} {sistema} — ya existe, saltando")
            resultado["skipped"].append(cur)
            cur += timedelta(days=1)
            continue

        try:
            client = ZeepClient(wsdl=_WSDL)
            archivo = client.service.GetEstadoCuentas(
                user, _PSSW, datetime(cur.year, cur.month, cur.day), sistema, "M024", None, "C"
            )

            destdir = _fecha_dir(cur)
            os.makedirs(destdir, exist_ok=True)

            for ec in archivo.EC.EdoCuenta:
                raw     = base64.b64encode(ec.File_C)
                decoded = base64.b64decode(raw)
                # Nombre del archivo dentro del ZIP (21 chars)
                name_start = decoded.find(b"E")
                full_name  = decoded[name_start: name_start + 44].decode()
                short_name = full_name[:21]

                with zipfile.ZipFile(io.BytesIO(decoded)) as zf:
                    extracted = zf.extract(full_name, destdir)

                dest = os.path.join(destdir, f"{short_name}.csv")
                if extracted != dest:
                    shutil.move(extracted, dest)

                print(f"[ECD] {cur} {sistema} — {short_name}.csv OK")

            resultado["ok"].append(cur)
        except Exception as e:
            print(f"[ECD] {cur} {sistema} — ERROR: {e}")
            resultado["error"].append(cur)

        time.sleep(0.5)
        cur += timedelta(days=1)

    return resultado


def list_available_dates(sistema: str = None, years: list = None) -> list[date]:
    """
    Devuelve lista de fechas para las que existen archivos ECD en la carpeta local.
    """
    if years is None:
        years = [str(y) for y in range(2022, 2027)]
    available = []
    for yr in years:
        yr_path = os.path.join(ECD_BASE, yr)
        if not os.path.isdir(yr_path):
            continue
        for mm in os.listdir(yr_path):
            mm_path = os.path.join(yr_path, mm)
            if not os.path.isdir(mm_path):
                continue
            for dd in os.listdir(mm_path):
                dd_path = os.path.join(mm_path, dd)
                if os.path.isdir(dd_path) and os.listdir(dd_path):
                    try:
                        d = date(int(yr), int(mm), int(dd))
                        if sistema is None or any(sistema in f for f in os.listdir(dd_path)):
                            available.append(d)
                    except ValueError:
                        pass
    return sorted(available)
