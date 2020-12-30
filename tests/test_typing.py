from bpc_utils import Linesep


def test_Linesep() -> None:
    assert Linesep.__class__.__module__ in {'typing', 'typing_extensions'}
