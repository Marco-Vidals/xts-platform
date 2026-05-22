@echo off
REM Ejecutar este archivo UNA SOLA VEZ como Administrador (click derecho -> Ejecutar como administrador)
REM Crea la tarea programada del ETL diario XTS a las 7:30 AM

set PYTHON=C:\Users\xiixt\AppData\Local\Programs\Python\Python312\python.exe
set WORKDIR=C:\Users\xiixt\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\XTS R&D\xts-platform

schtasks /create ^
  /tn "XTS ETL Diario" ^
  /tr "\"%PYTHON%\" -m etl.runner.daily_runner" ^
  /sc daily ^
  /st 07:30 ^
  /sd 05/10/2026 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% == 0 (
    echo.
    echo Tarea "XTS ETL Diario" creada correctamente.
    echo Correra todos los dias a las 07:30 AM.
) else (
    echo.
    echo ERROR: No se pudo crear la tarea. Asegurate de ejecutar como Administrador.
)
pause
