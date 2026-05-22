"""
Configuración Enverus Mosaic — entidades, datasets y modelos de forecast.
Para agregar pnodes o datasets: solo editar este archivo.
"""

# Regiones eólicas ERCOT
ERCOT_WIND_REGIONS = ["coastal", "north", "panhandle", "south", "west"]

# Modelos de forecast renovables
ERCOT_FORECAST_MODELS = ["RPP", "STPF", "HRRR", "ECMWF", "COP_HSL"]

# Entities para synthetic forecasts
# DC_L / DC_R (tie lines físicas ERCOT-México) no están modeladas en MarginalUnit.
# Usar zonas ERCOT del sur/oeste de Texas como proxy para precios frontera.
SYNTHETIC_ENTITIES = ["LZ_SOUTH", "LZ_WEST", "HB_SOUTH", "HB_WEST"]

# Datasets synthetic
SYNTHETIC_DATASETS = ["lmp_da", "lmp_rt", "as_da", "as_rt", "rtrdpa"]

# ISOs soportados
ISOS = ["ERCOT", "CAISO"]
