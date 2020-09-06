import pytest
from _pytest.monkeypatch import MonkeyPatch
from bpc_utils.typing import Generator


@pytest.fixture(scope='class')
def monkeypatch_class() -> Generator[MonkeyPatch, None, None]:
    """Class-scoped monkeypatch fixture."""
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()
