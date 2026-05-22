# =============================================================================
# XTS ETL — Deploy en Office Server
# Ejecutar como Administrador (PowerShell)
#
# Pre-requisitos manuales ANTES de correr este script:
#   1. Python 3.12 instalado (https://www.python.org/downloads/windows/)
#      - Marcar "Add python.exe to PATH"
#   2. ODBC Driver 17 for SQL Server instalado
#      (https://aka.ms/odbc17)
#   3. Git instalado (opcional, para clonar/actualizar repo)
#   4. Archivo .env creado en C:\XTS\xts-platform\Extractors\.env
#      (copiar de .env.example y llenar credenciales)
#
# Uso:
#   .\deploy_server.ps1
#   .\deploy_server.ps1 -RepoPath "D:\XTS\xts-platform\Extractors"
# =============================================================================

param(
    [string]$RepoPath = "C:\XTS\xts-platform\Extractors",
    [string]$LogPath  = "C:\XTS\logs"
)

$ErrorActionPreference = "Stop"
$PythonExe = "python"

Write-Host "=== XTS ETL Deploy ===" -ForegroundColor Cyan
Write-Host "RepoPath : $RepoPath"
Write-Host "LogPath  : $LogPath"
Write-Host ""

# ── 1. Verificar Python ───────────────────────────────────────────────────────
Write-Host "[1/5] Verificando Python..." -ForegroundColor Yellow
try {
    $pyVersion = & $PythonExe --version 2>&1
    Write-Host "      OK: $pyVersion"
} catch {
    Write-Error "Python no encontrado. Instalar desde https://www.python.org/downloads/windows/ y marcar 'Add to PATH'"
}

# ── 2. Verificar ODBC Driver 17 ───────────────────────────────────────────────
Write-Host "[2/5] Verificando ODBC Driver 17..." -ForegroundColor Yellow
$odbcKey = "HKLM:\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 17 for SQL Server"
if (Test-Path $odbcKey) {
    Write-Host "      OK: ODBC Driver 17 encontrado"
} else {
    Write-Warning "ODBC Driver 17 NO encontrado. Descargar de: https://aka.ms/odbc17"
    Write-Host "      Continuando de todas formas (puede fallar al conectar a DB)..."
}

# ── 3. Instalar dependencias Python ───────────────────────────────────────────
Write-Host "[3/5] Instalando dependencias pip..." -ForegroundColor Yellow
$reqFile = Join-Path $RepoPath "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Error "No se encontró requirements.txt en $reqFile"
}
& $PythonExe -m pip install --upgrade pip --quiet
& $PythonExe -m pip install -r $reqFile --quiet
Write-Host "      OK: dependencias instaladas"

# ── 4. Verificar .env ─────────────────────────────────────────────────────────
Write-Host "[4/5] Verificando .env..." -ForegroundColor Yellow
$envFile = Join-Path $RepoPath ".env"
if (-not (Test-Path $envFile)) {
    Write-Warning ".env NO encontrado en $envFile"
    $exampleFile = Join-Path $RepoPath ".env.example"
    if (Test-Path $exampleFile) {
        Copy-Item $exampleFile $envFile
        Write-Host "      Se copió .env.example → .env"
        Write-Host "      IMPORTANTE: Editar $envFile con credenciales reales antes de continuar" -ForegroundColor Red
        Write-Host "      Presiona Enter cuando hayas editado el archivo..."
        Read-Host
    } else {
        Write-Error "Tampoco existe .env.example. Crear .env manualmente."
    }
} else {
    Write-Host "      OK: .env encontrado"
}

# ── 5. Test de conexión a DB ──────────────────────────────────────────────────
Write-Host "[5/5] Probando conexión a DB..." -ForegroundColor Yellow
$testScript = @"
import sys
sys.path.insert(0, r'$RepoPath')
from etl.base.db import get_connection
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT @@VERSION')
    ver = cur.fetchone()[0].split('\n')[0]
    conn.close()
    print('OK:', ver)
except Exception as e:
    print('ERROR:', e)
    sys.exit(1)
"@
$result = & $PythonExe -c $testScript 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "      $result" -ForegroundColor Green
} else {
    Write-Warning "Fallo conexión DB: $result"
    Write-Host "      Verificar credenciales en .env y que el servidor DB sea accesible"
}

# ── Crear directorio de logs ───────────────────────────────────────────────────
Write-Host ""
Write-Host "Creando directorio de logs..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $LogPath | Out-Null
Write-Host "OK: $LogPath"

# ── Registrar tareas en Task Scheduler ────────────────────────────────────────
Write-Host ""
$schedulerScript = Join-Path $RepoPath "scripts\setup_scheduler.ps1"
$answer = Read-Host "Registrar tareas en Windows Task Scheduler? (s/n)"
if ($answer -eq "s" -or $answer -eq "S") {
    & $schedulerScript -PythonPath $PythonExe -RepoPath $RepoPath -LogPath $LogPath
} else {
    Write-Host "Omitido. Para registrar después: .\scripts\setup_scheduler.ps1"
}

Write-Host ""
Write-Host "=== Deploy completado ===" -ForegroundColor Green
Write-Host ""
Write-Host "Para probar manualmente:"
Write-Host "  cd $RepoPath"
Write-Host "  python -m etl.runner.run_all --schedule morning --desde 2026-04-07 --hasta 2026-04-07"
