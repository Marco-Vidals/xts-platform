# XTS Trading Platform

Plataforma de trading de energía para XTS - mercados CENACE, ERCOT, CAISO y Guatemala.

## Estructura

```
xts-platform/
  etl/
    cenace/       # Extracción CENACE (PML MDA/MTR)
    ercot/        # Extracción ERCOT via Enverus
    caiso/        # Extracción CAISO via Enverus
    guatemala/    # Extracción AMM Guatemala
    common/       # Conexión BD, utilidades compartidas
  app/
    morning/      # Dashboard Morning Trading
    afternoon/    # Dashboard Afternoon / Registro de trades
    backoffice/   # Settlements y facturación
  models/         # Modelos de forecast (ARIMAX, Monte Carlo, DART)
  db/             # Migraciones y scripts SQL
  config/         # Configuración (sin secrets en Git)
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

Copiar `config/config.example.py` a `config/secrets.py` y llenar credenciales.
