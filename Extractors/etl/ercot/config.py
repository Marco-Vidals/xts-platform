"""
Configuración ERCOT — nodos, zonas y regiones.
Para agregar un nodo: solo editar este archivo, el extractor lo toma automáticamente.
"""

# Settlement Points (precios DA/RT)
SETTLEMENT_POINTS = {
    "hubs": ["DC_L", "DC_R", "HB_BUSAVG", "HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"],
    "load_zones": [],  # Agregar después: LZ_AEN, LZ_CPS, LZ_HOUSTON, etc.
}

# Solo los nodos que se guardan en DATOS_ERCOT (legacy)
NODOS_DATOS_ERCOT = ["DC_L", "DC_R", "DC_E"]  # DC_E = Eagle Pass (actualmente cerrado)

# Weather zones para carga
WEATHER_ZONES = ["COAST", "EAST", "FAR_WEST", "NORTH", "NORTH_C", "SOUTH_C", "SOUTHERN", "WEST"]

# Regiones eólicas
WIND_REGIONS = ["coastal", "north", "panhandle", "south", "west"]

# Ancillary service types
AS_TYPES = ["REGUP", "REGDN", "RRSFFR", "RRSPFR", "ECRSM", "ECRSS", "NONSPIN"]
