import pytest
from bpc_utils import (Linesep, parse_boolean_state, parse_indentation, parse_linesep,
                       parse_positive_integer)
from bpc_utils.typing import Optional, Type, Union


@pytest.mark.parametrize(
    's,result',
    [
        (None, None),
        ('', None),
        ('1', 1),
        (1, 1),
        ('2', 2),
        (2, 2),
    ]
)
def test_parse_positive_integer(s: Optional[Union[str, int]], result: Optional[int]) -> None:
    assert parse_positive_integer(s) == result  # nosec


@pytest.mark.parametrize(
    's,exc,msg',
    [
        ('X', ValueError, "expect an integer value, got 'X'"),
        ('1.1', ValueError, "expect an integer value, got '1.1'"),
        (1.1, TypeError, "expect str or int, got 1.1"),
        ('0', ValueError, "expect integer value to be positive, got 0"),
        (0, ValueError, "expect integer value to be positive, got 0"),
        ('-1', ValueError, "expect integer value to be positive, got -1"),
        (-1, ValueError, "expect integer value to be positive, got -1"),
    ]
)
def test_parse_positive_integer_error(s: Optional[Union[str, int]], exc: Type[BaseException], msg: str) -> None:
    with pytest.raises(exc, match=msg):
        parse_positive_integer(s)


@pytest.mark.parametrize(
    's,result',
    [
        (None, None),
        ('1', True),
        ('yes', True),
        ('Y', True),
        ('True', True),
        ('ON', True),
        ('0', False),
        ('NO', False),
        ('n', False),
        ('FALSE', False),
        ('Off', False),
    ]
)
def test_parse_boolean_state(s: Optional[str], result: Optional[bool]) -> None:
    assert parse_boolean_state(s) == result  # nosec


@pytest.mark.parametrize(
    's,exc,msg',
    [
        ('', ValueError, "invalid boolean state value ''"),
        ('X', ValueError, "invalid boolean state value 'X'"),
    ]
)
def test_parse_boolean_state_error(s: Optional[str], exc: Type[BaseException], msg: str) -> None:
    with pytest.raises(exc, match=msg):
        parse_boolean_state(s)


@pytest.mark.parametrize(
    's,result',
    [
        (None, None),
        ('', None),
        ('\n', '\n'),
        ('\r\n', '\r\n'),
        ('\r', '\r'),
        ('LF', '\n'),
        ('CRLF', '\r\n'),
        ('cr', '\r'),
    ]
)
def test_parse_linesep(s: Optional[str], result: Optional[Linesep]) -> None:
    assert parse_linesep(s) == result  # nosec


@pytest.mark.parametrize(
    's,exc,msg',
    [
        ('X', ValueError, "invalid linesep value 'X'"),
    ]
)
def test_parse_linesep_error(s: Optional[str], exc: Type[BaseException], msg: str) -> None:
    with pytest.raises(exc, match=msg):
        parse_linesep(s)


@pytest.mark.parametrize(
    's,result',
    [
        (None, None),
        ('', None),
        ('t', '\t'),
        ('T', '\t'),
        ('tab', '\t'),
        ('Tab', '\t'),
        ('TAB', '\t'),
        ('\t', '\t'),
        ('2', ' ' * 2),
        (2, ' ' * 2),
        (' ' * 2, ' ' * 2),
        ('4', ' ' * 4),
        (4, ' ' * 4),
        (' ' * 4, ' ' * 4),
        ('8', ' ' * 8),
        (8, ' ' * 8),
        (' ' * 8, ' ' * 8),
    ]
)
def test_parse_indentation(s: Optional[Union[str, int]], result: Optional[str]) -> None:
    assert parse_indentation(s) == result  # nosec


@pytest.mark.parametrize(
    's,exc,msg',
    [
        ('X', ValueError, "invalid indentation value 'X'"),
        ('\t\t', ValueError, r"invalid indentation value '\\t\\t'"),
        ('\n', ValueError, r"invalid indentation value '\\n'"),
        ('0', ValueError, "invalid indentation value '0'"),
        (0, ValueError, "invalid indentation value 0"),
        ('-1', ValueError, "invalid indentation value '-1'"),
        (-1, ValueError, "invalid indentation value -1"),
        ('1.1', ValueError, "invalid indentation value '1.1'"),
        (1.1, TypeError, "expect str or int, got 1.1"),
    ]
)
def test_parse_indentation_error(s: Optional[Union[str, int]], exc: Type[BaseException], msg: str) -> None:
    with pytest.raises(exc, match=msg):
        parse_indentation(s)
