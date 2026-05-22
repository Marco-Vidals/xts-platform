"""
Wrapper — Trading / P&L
"""
import sys, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _ROOT)

import streamlit as st

if not st.session_state.get("logged_in"):
    try:
        st.switch_page("portal.py")
    except Exception:
        st.warning("Sesion no iniciada. Ve al portal principal.")
    st.stop()

_real_cfg = st.set_page_config
st.set_page_config = lambda *a, **kw: None

_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "trading_page.py"))
with open(_path, encoding="utf-8") as _f:
    _code = _f.read()

exec(compile(_code, _path, "exec"), {"__file__": _path, "__name__": "__main__", "__package__": None})  # noqa: S102

st.set_page_config = _real_cfg
