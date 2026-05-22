# =============================================================================
# XTS ETL — Configurar Windows Task Scheduler
# Ejecutar como Administrador en el Office Server
#
# Crea 3 tareas:
#   06:00 CST → corrida matutina (facts del día anterior)
#   14:00 CST → corrida de la tarde (forecasts actualizados)
#   23:30 CST → maintenance (backfill de gaps)
# =============================================================================

param(
    [string]$PythonPath = "python",
    [string]$RepoPath   = "C:\XTS\xts-platform\Extractors",
    [string]$LogPath    = "C:\XTS\logs"
)

$ErrorActionPreference = "Stop"

# Crear directorio de logs si no existe
New-Item -ItemType Directory -Force -Path $LogPath | Out-Null

function Register-EtlTask {
    param(
        [string]$TaskName,
        [string]$Args,
        [string]$Time
    )

    # Redirigir stdout+stderr a log con fecha → no se pierden errores
    $wrapperArgs = "/C cd /D `"$RepoPath`" && $PythonPath -m etl.runner.run_all $Args >> `"$LogPath\%DATE:~-4%-%DATE:~3,2%-%DATE:~0,2%_${TaskName}.log`" 2>&1"

    $action  = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument $wrapperArgs

    $trigger = New-ScheduledTaskTrigger -Daily -At $Time

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
        -RestartCount 2 `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action   $action `
        -Trigger  $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host "Tarea registrada: $TaskName @ $Time  (logs en $LogPath)"
}

# Corrida matutina 06:00 CST
Register-EtlTask `
    -TaskName "XTS-ETL-Morning" `
    -Args "--schedule morning" `
    -Time "06:00"

# Corrida de la tarde 14:00 CST
Register-EtlTask `
    -TaskName "XTS-ETL-Afternoon" `
    -Args "--schedule afternoon" `
    -Time "14:00"

# Maintenance 23:30 CST (backfill de gaps)
Register-EtlTask `
    -TaskName "XTS-ETL-Maintenance" `
    -Args "--schedule maintenance" `
    -Time "23:30"

Write-Host ""
Write-Host "=== Tareas ETL registradas en Windows Task Scheduler ==="
Get-ScheduledTask | Where-Object { $_.TaskName -like "XTS-ETL-*" } | Format-Table TaskName, State
