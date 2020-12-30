import enum
import io
import re
import socket

import pytest

from bpc_utils import (BPCSyntaxError, detect_encoding, detect_indentation, detect_linesep,
                       get_parso_grammar_versions, parso_parse)
from bpc_utils.parsing import PARSO_GRAMMAR_VERSIONS
from bpc_utils.typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpc_utils import Linesep
    from bpc_utils.typing import Optional, Tuple, Type, Union


class CodeType(enum.Enum):
    """Possible types for the ``code`` parameter."""
    STR = 0
    BYTES = 1
    TEXT_IO = 2
    PARSO_NODE = 3


def test_parso_grammar_versions() -> None:
    assert isinstance(PARSO_GRAMMAR_VERSIONS, list)
    assert isinstance(PARSO_GRAMMAR_VERSIONS[0], tuple)
    assert isinstance(PARSO_GRAMMAR_VERSIONS[0][0], int)
    assert isinstance(PARSO_GRAMMAR_VERSIONS[0][1], int)

    versions1 = get_parso_grammar_versions()
    assert len(versions1) > 1
    assert all(isinstance(x, str) for x in versions1)
    assert all(x.count('.') == 1 for x in versions1)

    versions2 = get_parso_grammar_versions(minimum=versions1[1])
    assert len(versions1) - len(versions2) == 1
    assert all(isinstance(x, str) for x in versions2)
    assert all(x.count('.') == 1 for x in versions2)

    versions3 = get_parso_grammar_versions(minimum='0.0')
    assert versions1 == versions3

    versions4 = get_parso_grammar_versions(minimum='3.10')
    assert all(isinstance(x, str) for x in versions4)
    assert all(x.count('.') == 1 for x in versions4)


@pytest.mark.parametrize(
    'minimum,exc,msg',
    [
        (3.8, TypeError, 'minimum version should be a string'),
        ('x.y', ValueError, 'invalid minimum version'),
        ('', ValueError, 'invalid minimum version'),
        ('3.8.3', ValueError, 'invalid minimum version'),
        ('3.08', ValueError, 'invalid minimum version'),
        ('03.8', ValueError, 'invalid minimum version'),
        ('3. 8', ValueError, 'invalid minimum version'),
        ('3 .8', ValueError, 'invalid minimum version'),
        ('+3.8', ValueError, 'invalid minimum version'),
        ('3.+8', ValueError, 'invalid minimum version'),
        ('3.-0', ValueError, 'invalid minimum version'),
    ]
)
def test_get_parso_grammar_versions_error(minimum: 'Optional[str]', exc: 'Type[BaseException]', msg: str) -> None:
    with pytest.raises(exc, match=re.escape(msg)):
        get_parso_grammar_versions(minimum)


def test_BPCSyntaxError() -> None:
    assert issubclass(BPCSyntaxError, SyntaxError)


@pytest.mark.parametrize(
    'code,result',
    [
        (b'# coding: gbk\n\xd6\xd0\xce\xc4', 'gbk'),
        (b'\xef\xbb\xbfhello', 'utf-8-sig'),
        (b'hello', 'utf-8'),
    ]
)
def test_detect_encoding(code: bytes, result: str) -> None:
    assert detect_encoding(code) == result


@pytest.mark.parametrize(
    'code,exc,msg',
    [
        ('hello', TypeError, "'code' should be bytes"),
    ]
)
def test_detect_encoding_error(code: bytes, exc: 'Type[BaseException]', msg: str) -> None:
    with pytest.raises(exc, match=re.escape(msg)):
        detect_encoding(code)


@pytest.mark.parametrize(
    'code,result',
    [
        ('1\n2\n3\n', '\n'),
        ('1\r2\r3\r', '\r'),
        ('1\r\n2\r\n3\r\n', '\r\n'),
        ('1\r2\r3\n', '\r'),
        ('1\n2\n3\r4\r', '\n'),
        ('1\n2\r\n3\r\n4\r5\r', '\r\n'),
        ('1\n2\n3\r4\f\r5\r\n6\r\n', '\n'),
    ]
)
@pytest.mark.parametrize('code_type', CodeType)
def test_detect_linesep(code_type: CodeType, code: str, result: 'Linesep') -> None:
    if code_type is CodeType.STR:
        assert detect_linesep(code) == result
    elif code_type is CodeType.BYTES:
        assert detect_linesep(code.encode()) == result
    elif code_type is CodeType.TEXT_IO:
        with io.StringIO(code, newline='') as file:
            assert detect_linesep(file) == result
    elif code_type is CodeType.PARSO_NODE:
        assert detect_linesep(parso_parse(code)) == result
    else:  # pragma: no cover
        raise ValueError('unknown code type')


def test_detect_linesep_unseekable_file() -> None:
    with socket.socket() as s:
        s.connect(('httpbin.org', 80))
        s.send(b'HEAD / HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n')
        with s.makefile(newline='') as file:
            assert detect_linesep(file) == '\r\n'


@pytest.mark.parametrize(
    'code,result',
    [
        ('foo', '    '),
        ('for x in [1]:\n    pass', '    '),
        ('for x in [1]:\n  pass', '  '),
        ('for x in [1]:\n\tpass', '\t'),
        ('for x in [1]:\n\t  pass', '    '),
        ('for x in [1]:\n\tpass\nfor x in [1]:\n    pass', '    '),
        ('for x in [1]:\n    pass\nfor x in [1]:\n  pass', '  '),
    ]
)
@pytest.mark.parametrize('code_type', CodeType)
def test_detect_indentation(code_type: CodeType, code: str, result: str) -> None:
    if code_type is CodeType.STR:
        assert detect_indentation(code) == result
    elif code_type is CodeType.BYTES:
        assert detect_indentation(code.encode()) == result
    elif code_type is CodeType.TEXT_IO:
        with io.StringIO(code, newline='') as file:
            assert detect_indentation(file) == result
    elif code_type is CodeType.PARSO_NODE:
        assert detect_indentation(parso_parse(code)) == result
    else:  # pragma: no cover
        raise ValueError('unknown code type')


def test_mixed_linesep_and_indentation() -> None:
    test_case = ('for x in [1]:\n    pass\rfor x in [1]:\r  pass', '\r', '  ')  # type: Tuple[str, Linesep, str]
    assert detect_linesep(test_case[0]) == test_case[1]
    assert detect_indentation(test_case[0]) == test_case[2]
    with io.StringIO(test_case[0], newline='') as file:
        assert detect_linesep(file) == test_case[1]
        assert detect_indentation(file) == test_case[2]


@pytest.mark.parametrize(
    'code,version',
    [
        ('1+1', None),
        (b'1+1', None),
        ('(x := 1)', '3.8'),
        (b'# coding: gbk\n\xd6\xd0\xce\xc4', None),
    ]
)
def test_parso_parse(code: 'Union[str, bytes]', version: 'Optional[str]') -> None:
    parso_parse(code, version=version)


@pytest.mark.parametrize(
    'code,filename,version,exc,msg',
    [
        ('(x := 1)', None, '3.7', BPCSyntaxError, "source file '<unknown>' contains the following syntax errors"),
        ('(x := 1)', 'temp', '3.7', BPCSyntaxError, "source file 'temp' contains the following syntax errors"),
        ('(x := 1)', '', '3.7', BPCSyntaxError, "source file '' contains the following syntax errors"),
        ('(x := 1)', None, '', ValueError, 'The given version is not in the right format.'),
    ]
)
def test_parso_parse_error(code: 'Union[str, bytes]', filename: 'Optional[str]', version: 'Optional[str]',
                           exc: 'Type[BaseException]', msg: str) -> None:
    with pytest.raises(exc, match=re.escape(msg)):
        parso_parse(code, filename=filename, version=version)
