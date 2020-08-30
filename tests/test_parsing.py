import enum
import io
import socket

import pytest
from bpc_utils import (BPCSyntaxError, detect_encoding, detect_indentation, detect_linesep,
                       get_parso_grammar_versions, parso_parse)
from bpc_utils.parsing import PARSO_GRAMMAR_VERSIONS


class CodeType(enum.Enum):
    """Possible types for the ``code`` parameter."""
    STR = 0
    BYTES = 1
    TEXT_IO = 2
    PARSO_NODE = 3


def test_parso_grammar_versions():
    assert isinstance(PARSO_GRAMMAR_VERSIONS, list)  # nosec
    assert isinstance(PARSO_GRAMMAR_VERSIONS[0], tuple)  # nosec

    versions1 = get_parso_grammar_versions()
    assert len(versions1) > 1  # nosec
    assert isinstance(versions1[0], str)  # nosec
    assert '.' in versions1[0]  # nosec

    versions2 = get_parso_grammar_versions(minimum=versions1[1])
    assert len(versions1) - len(versions2) == 1  # nosec

    with pytest.raises(ValueError, match='invalid minimum version'):
        get_parso_grammar_versions(3.8)
    with pytest.raises(ValueError, match='invalid minimum version'):
        get_parso_grammar_versions('x.y')


def test_BPCSyntaxError():
    assert issubclass(BPCSyntaxError, SyntaxError)  # nosec


@pytest.mark.parametrize(
    'code,result',
    [
        (b'# coding: gbk\n\xd6\xd0\xce\xc4', 'gbk'),
        (b'\xef\xbb\xbfhello', 'utf-8-sig'),
        (b'hello', 'utf-8'),
    ]
)
def test_detect_encoding(code, result):
    assert detect_encoding(code) == result  # nosec


@pytest.mark.parametrize(
    'code,exc,msg',
    [
        ('hello', TypeError, "'code' should be bytes"),
    ]
)
def test_detect_encoding_error(code, exc, msg):
    with pytest.raises(exc, match=msg):
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
def test_detect_linesep(code_type, code, result):
    if code_type is CodeType.STR:
        assert detect_linesep(code) == result  # nosec
    elif code_type is CodeType.BYTES:
        assert detect_linesep(code.encode()) == result  # nosec
    elif code_type is CodeType.TEXT_IO:
        with io.StringIO(code, newline='') as file:
            assert detect_linesep(file) == result  # nosec
    elif code_type is CodeType.PARSO_NODE:
        assert detect_linesep(parso_parse(code)) == result  # nosec
    else:  # pragma: no cover
        raise ValueError('unknown code type')


def test_detect_linesep_unseekable_file():
    with socket.socket() as s:
        s.connect(('httpbin.org', 80))
        s.send(b'HEAD / HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n')
        with s.makefile(newline='') as file:
            assert detect_linesep(file) == '\r\n'  # nosec


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
def test_detect_indentation(code_type, code, result):
    if code_type is CodeType.STR:
        assert detect_indentation(code) == result  # nosec
    elif code_type is CodeType.BYTES:
        assert detect_indentation(code.encode()) == result  # nosec
    elif code_type is CodeType.TEXT_IO:
        with io.StringIO(code, newline='') as file:
            assert detect_indentation(file) == result  # nosec
    elif code_type is CodeType.PARSO_NODE:
        assert detect_indentation(parso_parse(code)) == result  # nosec
    else:  # pragma: no cover
        raise ValueError('unknown code type')


def test_mixed_linesep_and_indentation():
    test_case = ('for x in [1]:\n    pass\rfor x in [1]:\r  pass', '\r', '  ')
    assert detect_linesep(test_case[0]) == test_case[1]  # nosec
    assert detect_indentation(test_case[0]) == test_case[2]  # nosec
    with io.StringIO(test_case[0], newline='') as file:
        assert detect_linesep(file) == test_case[1]  # nosec
        assert detect_indentation(file) == test_case[2]  # nosec


@pytest.mark.parametrize(
    'code,version',
    [
        ('1+1', None),
        (b'1+1', None),
        ('(x := 1)', '3.8'),
        (b'# coding: gbk\n\xd6\xd0\xce\xc4', None),
    ]
)
def test_parso_parse(code, version):
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
def test_parso_parse_error(code, filename, version, exc, msg):
    with pytest.raises(exc, match=msg):
        parso_parse(code, filename=filename, version=version)
