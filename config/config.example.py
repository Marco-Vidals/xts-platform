# config/secrets.py  <-- copia este archivo y llena los valores
# NO subir secrets.py a Git

# SQL Server (office server XTS)
DB_SERVER = "192.168.x.x"       # IP del office server
DB_PORT = 1433
DB_NAME = "XTS"
DB_USER = "xts_app"
DB_PASSWORD = "CAMBIAR"

# Enverus Mosaic API
ENVERUS_USER = "PEDIR_A_PEDRO"
ENVERUS_PASSWORD = "PEDIR_A_PEDRO"
ENVERUS_BASE_URL = "https://api-mosaic-prod.enverus.com/mosaic-api/"

# CENACE (pública, sin auth)
CENACE_BASE_URL = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"
