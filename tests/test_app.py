"""Smoke test: ejecuta TODAS las páginas con el AppTest oficial de Streamlit.

Si alguna página lanza una excepción, el test falla. Es la misma verificación
manual que se hizo página por página, automatizada para siempre.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = sorted(
    p for p in (ROOT / "pages").glob("*.py")
    if p.is_file() and not p.name.endswith(".backup")
)


def test_home():
    at = AppTest.from_file(str(ROOT / "Home.py"), default_timeout=60)
    at.run()
    assert not at.exception, f"Home.py lanzó excepción: {at.exception}"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_page(page: Path):
    at = AppTest.from_file(str(page), default_timeout=90)
    at.run()
    assert not at.exception, f"{page.name} lanzó excepción: {at.exception}"
