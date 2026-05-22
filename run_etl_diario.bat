@echo off
REM XTS ETL Diario — ejecutado por Windows Task Scheduler a las 7:30 AM
REM Actualiza todos los datos: ERCOT, CAISO, GTM, Temperaturas, Tipo de Cambio

cd /d "C:\Users\xiixt\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\XTS R&D\xts-platform"

"C:\Users\xiixt\AppData\Local\Programs\Python\Python312\python.exe" -m etl.runner.daily_runner

exit /b %ERRORLEVEL%
