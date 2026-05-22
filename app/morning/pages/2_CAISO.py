"""
Wrapper de página para CAISO Morning Dashboard.
No modificar — este archivo delega a caiso_morning.py.
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

# ── Ejecutar caiso_morning.py como si fuera el script principal ────────────────
# Parche temporal: set_page_config ya fue llamado por portal.py
_real_cfg = st.set_page_config
st.set_page_config = lambda *a, **kw: None  # no-op en paginas internas

_caiso_path = os.path.join(os.path.dirname(__file__), "..", "caiso_morning.py")
_caiso_path = os.path.abspath(_caiso_path)

with open(_caiso_path, encoding="utf-8") as _f:
    _code = _f.read()

exec(  # noqa: S102
    compile(_code, _caiso_path, "exec"),
    {
        "__file__":    _caiso_path,
        "__name__":    "__main__",
        "__package__": None,
    },
)

# Restaurar
st.set_page_config = _real_cfg
