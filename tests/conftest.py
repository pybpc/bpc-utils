import pytest
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture(scope='class')
def monkeypatch_class():
    """Class-scoped monkeypatch fixture."""
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()
