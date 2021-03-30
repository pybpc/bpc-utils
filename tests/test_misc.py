import collections.abc
import io
import re
import socket
import sys
import textwrap

import pytest

from bpc_utils import (BPCInternalError, Config, Placeholder, StringInterpolation, UUID4Generator,
                       first_non_none, first_truthy)
from bpc_utils.misc import MakeTextIO, current_time_with_tzinfo
from bpc_utils.typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpc_utils.typing import Generator, Set, T, Tuple, Type


def test_current_time_with_tzinfo() -> None:
    assert current_time_with_tzinfo().tzinfo is not None


@pytest.mark.parametrize(
    'args,result',
    [
        ((0, 1), 1),
        ((1, 0), 1),
        (([1],), 1),
        (([0, [0]],), [0]),
        (([{0}, 0],), {0}),
        (([],), None),
        (([''],), None),
        (([0, ()],), None),
        ((0, ()), None),
    ]
)
def test_first_truthy(args: 'Tuple[object]', result: object) -> None:
    assert first_truthy(*args) == result


@pytest.mark.parametrize(
    'args,exc,msg',
    [
        ((), TypeError, 'no arguments provided'),
        ((1,), TypeError, 'is not iterable'),
    ]
)
def test_first_truthy_error(args: 'Tuple[object]', exc: 'Type[BaseException]', msg: str) -> None:
    with pytest.raises(exc, match=re.escape(msg)):
        first_truthy(*args)


def test_first_truthy_short_circuit_usage() -> None:
    evaluated = set()  # type: Set[object]

    def log_evaluation(value: 'T') -> 'T':
        evaluated.add(value)
        return value

    def value_generator() -> 'Generator[object, None, None]':
        yield log_evaluation(0)
        yield log_evaluation(1)
        yield log_evaluation(2)  # pragma: no cover  # should not be evaluated

    assert first_truthy(value_generator()) == 1  # type: ignore[comparison-overlap]
    assert evaluated == {0, 1}


@pytest.mark.parametrize(
    'args,result',
    [
        ((0, 1), 0),
        ((1, 0), 1),
        ((None, 0), 0),
        ((0, None), 0),
        (([0],), 0),
        (([None, 0],), 0),
        (([0, None],), 0),
        (([],), None),
        (([None],), None),
        (([None, None],), None),
        ((None, None), None),
    ]
)
def test_first_non_none(args: 'Tuple[object]', result: object) -> None:
    assert first_non_none(*args) == result


@pytest.mark.parametrize(
    'args,exc,msg',
    [
        ((), TypeError, 'no arguments provided'),
        ((1,), TypeError, 'is not iterable'),
    ]
)
def test_first_non_none_error(args: 'Tuple[object]', exc: 'Type[BaseException]', msg: str) -> None:
    with pytest.raises(exc, match=re.escape(msg)):
        first_non_none(*args)


def test_first_non_none_short_circuit_usage() -> None:
    evaluated = set()  # type: Set[object]

    def log_evaluation(value: 'T') -> 'T':
        evaluated.add(value)
        return value

    def value_generator() -> 'Generator[object, None, None]':
        yield log_evaluation(None)
        yield log_evaluation(0)
        yield log_evaluation(1)  # pragma: no cover  # should not be evaluated

    assert first_non_none(value_generator()) == 0  # type: ignore[comparison-overlap]
    assert evaluated == {None, 0}


@pytest.mark.parametrize('dash', [True, False])
def test_uuid_gen(dash: bool) -> None:
    uuid_gen = UUID4Generator(dash=dash)
    uuids = [uuid_gen.gen() for _ in range(1000)]
    assert all(('-' in x) == dash for x in uuids)
    assert len(uuids) == len(set(uuids))


def test_MakeTextIO_str() -> None:
    with MakeTextIO('hello') as file:
        assert isinstance(file, io.StringIO)
        assert file.read() == 'hello'
    assert file.closed


def test_MakeTextIO_seekable_file() -> None:
    with io.StringIO('deadbeef') as sio:
        assert sio.seekable()
        sio.seek(2)
        assert sio.read(2) == 'ad'
        with MakeTextIO(sio) as file:
            assert file.read() == 'deadbeef'
        assert not sio.closed
        assert sio.tell() == 4


def test_MakeTextIO_unseekable_file() -> None:
    with socket.socket() as s:
        s.connect(('httpbin.org', 80))
        s.send(b'GET /anything HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n')
        with s.makefile() as file1:
            assert not file1.seekable()
            with MakeTextIO(file1) as file2:
                data = file2.read()
                assert data.startswith('HTTP/1.1 200 OK')


def test_Config() -> None:
    config = Config(foo='var', bar=True, boo=1)
    assert isinstance(config, collections.abc.MutableMapping)
    assert config.foo == 'var'  # type: ignore[attr-defined]  # pylint: disable=no-member
    assert config.bar is True  # type: ignore[attr-defined]  # pylint: disable=no-member
    assert config.boo == 1  # type: ignore[attr-defined]  # pylint: disable=no-member
    assert config['foo'] == 'var'
    assert config['bar'] is True
    assert config['boo'] == 1
    assert 'foo' in config
    assert 'moo' not in config
    assert '666' not in config
    assert len(config) == 3
    assert repr(config) == "Config(bar=True, boo=1, foo='var')"

    config['666'] = '777'
    assert '666' in config
    assert config['666'] == '777'

    setattr(config, '666', '888')
    assert config['666'] == '888'

    del config['666']
    assert '666' not in config

    delattr(config, 'foo')
    assert 'foo' not in config

    del config.bar  # type: ignore[attr-defined]  # pylint: disable=no-member
    assert 'bar' not in config
    assert len(config) == 1
    for key, value in config.items():
        assert key == 'boo'
        assert value == 1

    config.xxx = 'yyy'  # type: ignore[attr-defined]
    assert 'xxx' in config
    assert config['xxx'] == 'yyy'

    assert dict(Config(a=1, b=2)) == {'a': 1, 'b': 2}
    assert Config(a=1, b=2) == Config(b=2, a=1)
    assert Config(a=1, b=2) != {'a': 1, 'b': 2}
    assert Config(a=1, b=2) != Config(b=1, a=2)

    assert repr(Config(**{'z': 1, 'y': '2'})) == "Config(y='2', z=1)"
    assert repr(Config(**{'z': True, '@': []})) == "Config(z=True, **{'@': []})"
    assert repr(Config(**{'z': (), '8': 2})) == "Config(z=(), **{'8': 2})"
    assert repr(Config(zz='zoo', **{'z': 1, 'return': 2})) == "Config(z=1, zz='zoo', **{'return': 2})"
    assert repr(Config(**{'z': 1, '__debug__': {}})) == "Config(z=1, **{'__debug__': {}})"
    assert repr(Config(**{'return': 0})) == "Config(**{'return': 0})"
    if sys.version_info[:2] >= (3, 6):  # dict preserves insertion order  # pragma: no cover
        assert repr(Config(**{'z': 1, 'return': 2, '8': 3})) == "Config(z=1, **{'8': 3, 'return': 2})"
        assert repr(Config(**{'return': 0, '8': 3})) == "Config(**{'8': 3, 'return': 0})"


def test_string_interpolation() -> None:
    assert Placeholder('p1').name == 'p1'

    with pytest.raises(TypeError, match='placeholder name must be str'):
        Placeholder(1)  # type: ignore[arg-type]

    assert Placeholder('p1') == Placeholder('p1')
    assert Placeholder('p1') != Placeholder('p2')
    assert Placeholder('p1') != 'p1'
    assert Placeholder('p1')

    assert repr(Placeholder('p1')) == "Placeholder('p1')"

    assert hash(Placeholder('p1')) == hash(Placeholder('p1'))

    assert StringInterpolation() == StringInterpolation()
    assert StringInterpolation('') == StringInterpolation()
    assert not StringInterpolation()
    assert StringInterpolation() == ''  # pylint: disable=compare-to-empty-string

    assert StringInterpolation('x') == StringInterpolation('x')
    assert StringInterpolation('x') != StringInterpolation('y')
    assert StringInterpolation('x') == 'x'
    assert StringInterpolation('x') != 'y'
    assert StringInterpolation('x')

    assert StringInterpolation(Placeholder('y')) == StringInterpolation(Placeholder('y'))
    assert StringInterpolation(Placeholder('y')) == Placeholder('y')
    assert StringInterpolation(Placeholder('y')) != Placeholder('z')
    assert StringInterpolation(Placeholder('y'))
    assert StringInterpolation(Placeholder('y')) != StringInterpolation(Placeholder('y'), 'z')
    assert StringInterpolation(Placeholder('y')) != StringInterpolation(Placeholder('z'))
    assert StringInterpolation(Placeholder('y')) != StringInterpolation('y')

    assert StringInterpolation(Placeholder('y'), 'z', 'x')
    assert StringInterpolation(Placeholder('y'), 'z', 'x') == StringInterpolation(Placeholder('y'), 'zx')
    assert StringInterpolation(Placeholder('y'), 'z', 'x') != StringInterpolation('yz', Placeholder('x'))

    assert repr(StringInterpolation()) == 'StringInterpolation()'
    assert repr(StringInterpolation('')) == 'StringInterpolation()'
    assert repr(StringInterpolation('x')) == "StringInterpolation('x')"
    assert repr(StringInterpolation(Placeholder('y'))) == "StringInterpolation(Placeholder('y'))"
    assert repr(StringInterpolation(Placeholder('y'), '')) == "StringInterpolation(Placeholder('y'))"
    assert repr(StringInterpolation(Placeholder('y'), 'z', 'x')) == "StringInterpolation(Placeholder('y'), 'zx')"

    assert hash(StringInterpolation()) == hash('')
    assert hash(StringInterpolation('x')) == hash('x')
    assert hash(StringInterpolation(Placeholder('y'))) == hash(Placeholder('y'))
    assert (hash(StringInterpolation(Placeholder('y'), 'z', 'x'))
            == hash(StringInterpolation(Placeholder('y'), 'z', 'x')))

    assert Placeholder('p1') + '' == StringInterpolation(Placeholder('p1'))
    assert Placeholder('p1') + 'suffix' == StringInterpolation(Placeholder('p1'), 'suffix')
    assert Placeholder('p1') + Placeholder('p2') == StringInterpolation(Placeholder('p1'), Placeholder('p2'))
    assert (Placeholder('p1') + StringInterpolation('infix', Placeholder('p2'))
            == StringInterpolation(Placeholder('p1'), 'infix', Placeholder('p2')))

    assert '' + Placeholder('p1') == StringInterpolation(Placeholder('p1'))
    assert 'prefix' + Placeholder('p1') == StringInterpolation('prefix', Placeholder('p1'))
    assert (StringInterpolation(Placeholder('p1'), 'infix') + Placeholder('p2')
            == StringInterpolation(Placeholder('p1'), 'infix', Placeholder('p2')))

    assert (StringInterpolation('prefix', Placeholder('p1')) + 'suffix'
            == StringInterpolation('prefix', Placeholder('p1'), 'suffix'))
    assert ('prefix' + StringInterpolation(Placeholder('p1'), 'suffix')
            == StringInterpolation('prefix', Placeholder('p1'), 'suffix'))

    assert StringInterpolation() + StringInterpolation() == StringInterpolation()
    assert StringInterpolation() + StringInterpolation('x') == StringInterpolation('x')
    assert StringInterpolation(Placeholder('x')) + StringInterpolation() == StringInterpolation(Placeholder('x'))
    assert (StringInterpolation(Placeholder('x')) + StringInterpolation('y')
            == StringInterpolation(Placeholder('x'), 'y'))
    assert (StringInterpolation(Placeholder('x')) + StringInterpolation(Placeholder('y'))
            == StringInterpolation(Placeholder('x'), Placeholder('y')))
    assert (StringInterpolation(Placeholder('x')) + StringInterpolation(Placeholder('y'), 'z')
            == StringInterpolation(Placeholder('x'), Placeholder('y'), 'z'))

    with pytest.raises(TypeError):
        Placeholder('x') + 1  # pylint: disable=expression-not-assigned
    with pytest.raises(TypeError):
        1 + Placeholder('x')  # pylint: disable=expression-not-assigned
    with pytest.raises(TypeError):
        StringInterpolation() + 1  # pylint: disable=expression-not-assigned
    with pytest.raises(TypeError):
        1 + StringInterpolation()  # pylint: disable=expression-not-assigned

    assert StringInterpolation.from_components(
        ('prefix', 'infix', 'suffix'),
        (Placeholder('data1'), Placeholder('data2'))
    ) == StringInterpolation('prefix', Placeholder('data1'), 'infix', Placeholder('data2'), 'suffix')
    assert StringInterpolation.from_components(
        (x for x in ('prefix', 'infix', 'suffix')),
        (x for x in (Placeholder('data1'), Placeholder('data2')))
    ) == StringInterpolation('prefix', Placeholder('data1'), 'infix', Placeholder('data2'), 'suffix')
    with pytest.raises(TypeError, match='literals must be a non-string iterable'):
        StringInterpolation.from_components('a', ())
    with pytest.raises(ValueError, match='the number of literals must be exactly one more '
                                         'than the number of placeholders'):
        StringInterpolation.from_components((), ())
    with pytest.raises(TypeError, match='literals contain non-string value: 1'):
        StringInterpolation.from_components((1,), ())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match='placeholders contain non-Placeholder value: 2'):
        StringInterpolation.from_components(('a', 'b'), (2,))  # type: ignore[arg-type]

    assert list(StringInterpolation(
        'prefix', Placeholder('data'), 'suffix'
    ).iter_components()) == ['prefix', Placeholder('data'), 'suffix']
    assert list(StringInterpolation(
        'prefix', Placeholder('data')
    ).iter_components()) == ['prefix', Placeholder('data'), '']
    assert list(StringInterpolation().iter_components()) == ['']

    si1 = StringInterpolation('s1', Placeholder('q1'), 's2', Placeholder('q2'), 's3', Placeholder('q3'))
    si2 = si1 % {'q1': '%s %(q2)s %(q3)s %', 'q2': '{q3}'}
    si3 = si2 % {'q3': 66, 'extra': 'unused'}
    assert si2 == StringInterpolation('s1%s %(q2)s %(q3)s %s2{q3}s3', Placeholder('q3'))
    assert si3 == StringInterpolation('s1%s %(q2)s %(q3)s %s2{q3}s366')
    assert si3.result == 's1%s %(q2)s %(q3)s %s2{q3}s366'
    with pytest.raises(ValueError, match="string interpolation not complete, "
                                         "the following placeholders have not been substituted: 'q3'"):
        si2.result  # pylint: disable=pointless-statement
    with pytest.raises(ValueError, match="string interpolation not complete, "
                                         "the following placeholders have not been substituted: 'q1', 'q2', 'q3'"):
        si1.result  # pylint: disable=pointless-statement
    assert si3 % {'even': 'more'} == si3

    assert (StringInterpolation(
                Placeholder('x'), ' and ', Placeholder('x')
            ) % {'x': 'banana'}).result == 'banana and banana'


@pytest.mark.parametrize(
    'message,context,exc,excmsg',
    [
        ('Stack overflow!\nStack overflow again!', 'bpc-utils', BPCInternalError, textwrap.dedent('''\
            An internal bug happened in bpc-utils:

            Stack overflow!
            Stack overflow again!

            Please report this error to project maintainers.''')),
        (666, 'bpc-utils', BPCInternalError, textwrap.dedent('''\
            An internal bug happened in bpc-utils:

            666

            Please report this error to project maintainers.''')),
        ('\t', 'bpc-utils', ValueError, 'message should not be empty'),
        ('Stack overflow!', 666, TypeError, 'context should be str'),
        ('Stack overflow!', ' ', ValueError, 'context should not be empty'),
    ]
)
def test_BPCInternalError(message: object, context: str, exc: 'Type[BaseException]', excmsg: str) -> None:
    with pytest.raises(exc, match=re.escape(excmsg)):
        raise BPCInternalError(message, context)
