from bpc_utils.typing import TYPE_CHECKING

# Types of builtin pytest fixtures are exported since pytest version 6.2
# See https://docs.pytest.org/en/stable/changelog.html#pytest-6-2-0-2020-12-12
try:
    from pytest import MonkeyPatch
except ImportError:  # pragma: no cover
    from _pytest.monkeypatch import MonkeyPatch


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
    try:
        from pytest import CaptureFixture  # pylint: disable=W0611,C0412
    except ImportError:
        from _pytest.capture import CaptureFixture  # noqa: F401  # pylint: disable=C0412

    try:
        from pytest import TempPathFactory  # pylint: disable=W0611,C0412
    except ImportError:
        from _pytest.tmpdir import TempPathFactory  # noqa: F401  # pylint: disable=C0412

    __all__.extend(['CaptureFixture', 'TempPathFactory'])
