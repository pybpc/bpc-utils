from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from _pytest.tmpdir import TempPathFactory


def read_text_file(filename: str, encoding: str = 'utf-8') -> str:
    """Read text file."""
    with open(filename, 'r', encoding=encoding) as file:
        return file.read()


def write_text_file(filename: str, content: str, encoding: str = 'utf-8') -> None:
    """Write text file."""
    with open(filename, 'w', encoding=encoding) as file:
        file.write(content)


__all__ = ['CaptureFixture', 'MonkeyPatch', 'TempPathFactory', 'read_text_file', 'write_text_file']
