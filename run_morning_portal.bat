@echo off
REM XTS Morning Portal — Portal unificado ERCOT + CAISO
REM Doble click para abrir el portal de mañana

cd /d "C:\Users\xiixt\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\XTS R&D\xts-platform"

echo.
echo  =====================================
echo   XTS Morning Portal  v1.1.0
echo   Abriendo en http://localhost:8501
echo  =====================================
echo.

"C:\Users\xiixt\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run app/morning/portal.py --server.port 8501 --server.headless false --browser.gatherUsageStats false

pause
