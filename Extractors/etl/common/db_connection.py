"""
Wrapper de backward compatibilidad.
El código nuevo debe usar: from etl.base.db import get_connection
"""
from etl.base.db import get_connection  # noqa: F401
