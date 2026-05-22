"""
Configuración CAISO — nodos y nodos frontera CENACE-BCA.
Para agregar un nodo: solo editar este archivo.
"""

# Nodos CAISO (precios DA/FMM)
NODES = ["ROA-230_2_N101", "TJI-230_2_N101"]  # Agregar más después

# Alias cortos para columnas en DATOS_CAISO
NODE_ALIASES = {
    "ROA-230_2_N101": "ROA",
    "TJI-230_2_N101": "TJI",
}

# Nodos frontera CENACE-BCA (PML via CENACE API)
CENACE_BORDER_NODES = {
    "BCA": ["07IVY-230", "07OMS-230"],
}

CENACE_NODE_ALIASES = {
    "07IVY-230": "IVY",
    "07OMS-230": "OMS",
}
