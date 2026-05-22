"""
Navega el filesystem del EC2 via xp_cmdshell y descarga todos los .py del usuario xiixt
"""
import pyodbc, os, pathlib

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=ec2-34-203-113-74.compute-1.amazonaws.com,1433;"
    "DATABASE=master;UID=sa;PWD=XTS_operations.XiiX;"
    "TrustServerCertificate=yes;Connection Timeout=15;"
)

BACKUP_DIR = pathlib.Path(__file__).parent.parent / "extractors"
BACKUP_DIR.mkdir(exist_ok=True)

conn = pyodbc.connect(CONN_STR)
cur  = conn.cursor()

def cmd(c):
    cur.execute("EXEC xp_cmdshell ?", [c])
    return [r[0] for r in cur.fetchall() if r[0]]

def read_file(path):
    cur.execute("EXEC xp_cmdshell ?", [f'type "{path}"'])
    lines = [r[0] for r in cur.fetchall()]
    return "\n".join(l if l is not None else "" for l in lines)

# Buscar .py SOLO en carpeta del usuario xiixt y Desktop/Documents
search_roots = [
    r"C:\Users\xiixt",
    r"C:\Users\Administrator",
    r"C:\Users\Administator",
    r"C:\XTS",
    r"C:\Scripts",
    r"C:\ETL",
    r"C:\Python",
]

all_py = []
for root in search_roots:
    result = cmd(f'dir "{root}" /S /B /A:-D 2>nul | findstr /I "\\.py$"')
    if result and "File Not Found" not in str(result) and "no encuentra" not in str(result[0]).lower():
        print(f"[{root}] {len(result)} archivos .py")
        for f in result:
            print(f"  {f}")
        all_py.extend(result)

print(f"\nTotal .py encontrados: {len(all_py)}")

# Descargar cada .py
print(f"\n=== Descargando a {BACKUP_DIR} ===")
saved = 0
for remote_path in all_py:
    try:
        safe = remote_path.replace(":\\", "__").replace("\\", "_").replace("/", "_")
        local_path = BACKUP_DIR / (safe + ".txt")
        content = read_file(remote_path)
        local_path.write_text(content, encoding="utf-8", errors="replace")
        print(f"  OK  {remote_path}")
        saved += 1
    except Exception as e:
        print(f"  ERR {remote_path}: {e}")

print(f"\nTotal guardados: {saved} archivos en {BACKUP_DIR}")
conn.close()
