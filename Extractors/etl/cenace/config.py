"""
Configuración CENACE — nodos P frontera y zonas de precios.
Para agregar un nodo: solo editar este archivo.
"""

# Nodos P frontera (7 prioritarios)
NODOS_P_PRIORITARIOS = {
    "BCA": ["07IVY-230", "07OMS-230", "07ENS-230", "07MXL-230", "07TIJ-230"],
    "SIN": ["06LAA-138", "06RRD-138", "09LBR-230"],
    # Agregar más sin tocar código extractor
}

# Alias cortos para tablas y columnas
NODO_ALIASES = {
    "07IVY-230": "IVY",
    "07OMS-230": "OMS",
    "07ENS-230": "ENS",
    "07MXL-230": "MXL",
    "07TIJ-230": "TIJ",
    "06LAA-138": "LAA",
    "06RRD-138": "RRD",
    "09LBR-230": "LBR",
}

# Sistemas y sus zonas de precio
SISTEMAS = {
    "SIN": 101,   # 101 zonas
    "BCA": 4,     # 4 zonas
    "BCS": 3,     # 3 zonas
}
