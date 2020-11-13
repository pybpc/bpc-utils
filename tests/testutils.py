from _pytest.monkeypatch import MonkeyPatch

from bpc_utils.typing import TYPE_CHECKING


def read_text_file(filename: str, encoding: str = 'utf-8') -> str:
    """Read text file."""
    with open(filename, 'r', encoding=encoding) as file:
        return file.read()


def write_text_file(filename: str, content: str, encoding: str = 'utf-8') -> None:
    """Write text file."""
    with open(filename, 'w', encoding=encoding) as file:
        file.write(content)


__all__ = ['MonkeyPatch', 'read_text_file', 'write_text_file']

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture  # noqa: F401  # pylint: disable=ungrouped-imports
    from _pytest.tmpdir import TempPathFactory  # noqa: F401  # pylint: disable=ungrouped-imports
    __all__.extend(['CaptureFixture', 'TempPathFactory'])
