@echo off
cd /d "C:\Users\xiixt\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\XTS R&D\xts-platform"
"C:\Users\xiixt\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run app/afternoon/portal.py --server.port 8502 --server.headless false
pause
