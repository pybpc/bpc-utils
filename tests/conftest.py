import pytest

from bpc_utils.typing import TYPE_CHECKING

from .testutils import MonkeyPatch

if TYPE_CHECKING:
    from bpc_utils.typing import Generator


@pytest.fixture(scope='class')
def monkeypatch_class() -> 'Generator[MonkeyPatch, None, None]':
    """Class-scoped monkeypatch fixture."""
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()
