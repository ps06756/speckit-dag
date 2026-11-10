import pytest

from .helpers import EXAMPLE, build


@pytest.fixture
def example_graph():
    return build(EXAMPLE.read_text(encoding="utf-8"))
