param()
$ok   = " OK    "
$warn = " FALTA "

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  XTS ETL -- Diagnostico del servidor"
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Python
Write-Host "-- Python --"
try {
    $v = & python --version 2>&1
    Write-Host "$ok $v" -ForegroundColor Green
} catch {
    Write-Host "$warn Python no en PATH  -> https://www.python.org/downloads/windows/" -ForegroundColor Red
}

# pip packages
Write-Host ""
Write-Host "-- Paquetes Python --"
foreach ($pkg in @("pandas","requests","pyodbc","openpyxl","lxml")) {
    $v = & python -c "import $pkg; print($pkg.__version__)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "$ok $pkg $v" -ForegroundColor Green
    } else {
        Write-Host "$warn $pkg no instalado" -ForegroundColor Yellow
    }
}

# ODBC Driver 17
Write-Host ""
Write-Host "-- ODBC Driver 17 --"
if (Test-Path "HKLM:\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 17 for SQL Server") {
    Write-Host "$ok ODBC Driver 17 for SQL Server" -ForegroundColor Green
} else {
    Write-Host "$warn No encontrado -> https://aka.ms/odbc17" -ForegroundColor Red
}

# Git
Write-Host ""
Write-Host "-- Git --"
try {
    $v = & git --version 2>&1
    Write-Host "$ok $v" -ForegroundColor Green
} catch {
    Write-Host "$warn Git no encontrado (opcional)" -ForegroundColor Yellow
}

# Tailscale
Write-Host ""
Write-Host "-- Tailscale --"
try {
    $tsStatus = & tailscale status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "$ok Tailscale activo" -ForegroundColor Green
        $line = $tsStatus | Select-String "^\d" | Select-Object -First 1
        if ($line) { Write-Host "       $line" }
    } else {
        Write-Host "$warn Tailscale no conectado" -ForegroundColor Yellow
    }
} catch {
    Write-Host "$warn Tailscale no instalado -> https://tailscale.com/download" -ForegroundColor Red
}

# Conectividad SQL Server
Write-Host ""
Write-Host "-- Conectividad SQL Server (100.70.216.12:1433) --"
$tcp = New-Object System.Net.Sockets.TcpClient
try {
    $tcp.Connect("100.70.216.12", 1433)
    Write-Host "$ok Puerto 1433 accesible" -ForegroundColor Green
    $tcp.Close()
} catch {
    Write-Host "$warn No se puede conectar -> revisar Tailscale / firewall" -ForegroundColor Red
}

# Repo
Write-Host ""
Write-Host "-- Repo ETL --"
$repoCandidates = @(
    "C:\XTS\xts-platform\Extractors",
    "$env:USERPROFILE\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\XTS R&D\xts-platform\Extractors"
)
$repoFound = $null
foreach ($p in $repoCandidates) {
    if (Test-Path "$p\etl\runner\run_all.py") {
        Write-Host "$ok Repo en: $p" -ForegroundColor Green
        $repoFound = $p
        break
    }
}
if (-not $repoFound) {
    Write-Host "$warn Repo no encontrado (buscado en C:\XTS\ y OneDrive)" -ForegroundColor Yellow
}

# .env
Write-Host ""
Write-Host "-- Archivo .env --"
if ($repoFound) {
    $envFile = "$repoFound\.env"
    if (Test-Path $envFile) {
        Write-Host "$ok .env existe" -ForegroundColor Green
        $content = Get-Content $envFile
        foreach ($key in @("XTS_DB_SERVER","XTS_DB_PASSWORD","ERCOT_OCP_KEY","MU_USERNAME")) {
            $line = $content | Where-Object { $_ -match "^$key=.+" }
            if ($line) {
                Write-Host "   $ok $key configurado" -ForegroundColor Green
            } else {
                Write-Host "   $warn $key vacio" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "$warn .env NO existe -> copiar .env.example y llenar" -ForegroundColor Red
    }
} else {
    Write-Host "$warn No se puede verificar (repo no encontrado)" -ForegroundColor Yellow
}

# Task Scheduler
Write-Host ""
Write-Host "-- Tareas Task Scheduler --"
$tareas = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "XTS-ETL-*" }
if ($tareas) {
    $tareas | Format-Table TaskName, State -AutoSize
} else {
    Write-Host "$warn No hay tareas XTS-ETL-* registradas" -ForegroundColor Yellow
}

# Disco
Write-Host ""
Write-Host "-- Disco C: --"
$disk = Get-PSDrive C
Write-Host "$ok Libre: $([math]::Round($disk.Free/1GB,1)) GB  |  Usado: $([math]::Round($disk.Used/1GB,1)) GB"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Copia este output y envialo"
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""
