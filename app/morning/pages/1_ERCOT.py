"""
Wrapper de página para ERCOT Morning Dashboard.
No modificar — este archivo delega a ercot_morning.py.
Correr como parte del portal: streamlit run app/morning/portal.py
"""
import sys
import os

# Path raiz del proyecto
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _ROOT)

import streamlit as st

# ── Auth check ─────────────────────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    try:
        st.switch_page("portal.py")
    except Exception:
        st.warning("Sesion no iniciada. Ve al portal principal.")
    st.stop()

# ── Ejecutar ercot_morning.py como si fuera el script principal ────────────────
# Parche temporal: set_page_config ya fue llamado por portal.py
_real_cfg = st.set_page_config
st.set_page_config = lambda *a, **kw: None  # no-op en paginas internas

_ercot_path = os.path.join(os.path.dirname(__file__), "..", "ercot_morning.py")
_ercot_path = os.path.abspath(_ercot_path)

with open(_ercot_path, encoding="utf-8") as _f:
    _code = _f.read()

exec(  # noqa: S102
    compile(_code, _ercot_path, "exec"),
    {
        "__file__":    _ercot_path,
        "__name__":    "__main__",
        "__package__": None,
    },
)

# Restaurar
st.set_page_config = _real_cfg
