#!/bin/bash
# XTS ETL -- Diagnostico del servidor Linux
# Correr: bash check_server.sh

OK="  OK   "
FALTA=" FALTA "

echo ""
echo "======================================="
echo "  XTS ETL -- Diagnostico del servidor"
echo "======================================="
echo ""

# Python3
echo "-- Python --"
if command -v python3 &>/dev/null; then
    echo "$OK $(python3 --version)"
else
    echo "$FALTA python3 no encontrado  ->  sudo apt install python3 python3-pip"
fi

# pip3
echo ""
echo "-- pip --"
if command -v pip3 &>/dev/null; then
    echo "$OK $(pip3 --version)"
else
    echo "$FALTA pip3 no encontrado  ->  sudo apt install python3-pip"
fi

# Paquetes Python
echo ""
echo "-- Paquetes Python --"
for pkg in pandas requests pyodbc openpyxl lxml; do
    v=$(python3 -c "import $pkg; print($pkg.__version__)" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "$OK $pkg $v"
    else
        echo "$FALTA $pkg no instalado"
    fi
done

# ODBC Driver 17
echo ""
echo "-- ODBC Driver 17 for SQL Server --"
if odbcinst -q -d -n "ODBC Driver 17 for SQL Server" 2>/dev/null | grep -q Driver; then
    echo "$OK ODBC Driver 17 encontrado"
elif [ -f /opt/microsoft/msodbcsql17/lib64/libmsodbcsql-17*.so* ] 2>/dev/null; then
    echo "$OK ODBC Driver 17 encontrado (manual)"
else
    echo "$FALTA No encontrado"
    echo "       Instalar:"
    echo "       curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -"
    echo "       curl https://packages.microsoft.com/config/ubuntu/\$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list"
    echo "       sudo apt-get update && sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev"
fi

# Git
echo ""
echo "-- Git --"
if command -v git &>/dev/null; then
    echo "$OK $(git --version)"
else
    echo "$FALTA git no encontrado  ->  sudo apt install git"
fi

# Conectividad SQL Server
echo ""
echo "-- Conectividad SQL Server (100.70.216.12:1433) --"
if timeout 3 bash -c "echo >/dev/tcp/100.70.216.12/1433" 2>/dev/null; then
    echo "$OK Puerto 1433 accesible"
else
    echo "$FALTA No se puede conectar a 100.70.216.12:1433"
fi

# Repo
echo ""
echo "-- Repo ETL --"
REPO_PATH=""
for p in "/opt/xts/xts-platform/Extractors" "$HOME/xts-platform/Extractors" "/home/xts/xts-platform/Extractors"; do
    if [ -f "$p/etl/runner/run_all.py" ]; then
        echo "$OK Repo en: $p"
        REPO_PATH=$p
        break
    fi
done
if [ -z "$REPO_PATH" ]; then
    echo "$FALTA Repo no encontrado (aun no deployado)"
fi

# .env
echo ""
echo "-- Archivo .env --"
if [ -n "$REPO_PATH" ] && [ -f "$REPO_PATH/.env" ]; then
    echo "$OK .env existe"
    for key in XTS_DB_SERVER XTS_DB_PASSWORD ERCOT_OCP_KEY MU_USERNAME; do
        val=$(grep "^$key=" "$REPO_PATH/.env" | cut -d= -f2)
        if [ -n "$val" ]; then
            echo "    $OK $key configurado"
        else
            echo "    $FALTA $key vacio"
        fi
    done
else
    echo "$FALTA .env no existe"
fi

# Cron
echo ""
echo "-- Cron jobs ETL --"
if crontab -l 2>/dev/null | grep -q "run_all.py"; then
    echo "$OK Cron jobs registrados:"
    crontab -l | grep "run_all.py"
else
    echo "$FALTA No hay cron jobs XTS registrados"
fi

# Disco
echo ""
echo "-- Disco --"
df -h / | tail -1 | awk '{print "  Usado: "$3"  Libre: "$4"  Total: "$2}'

# Info del sistema
echo ""
echo "-- Sistema --"
echo "  OS: $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY | cut -d= -f2)"
echo "  Hostname: $(hostname)"
echo "  User: $(whoami)"

echo ""
echo "======================================="
echo "  Copia este output y envialo"
echo "======================================="
echo ""
