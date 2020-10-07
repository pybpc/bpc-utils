import pytest
from bpc_utils.typing import Generator

from .testutils import MonkeyPatch


@pytest.fixture(scope='class')
def monkeypatch_class() -> Generator[MonkeyPatch, None, None]:
    """Class-scoped monkeypatch fixture."""
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()
