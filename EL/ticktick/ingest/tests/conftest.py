import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text())

    return _load
