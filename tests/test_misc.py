import collections.abc
import io
import re
import socket
import sys

import pytest

from bpc_utils import Config, UUID4Generator, first_non_none, first_truthy
from bpc_utils.misc import MakeTextIO
from bpc_utils.typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpc_utils.typing import Generator, Set, T, Tuple, Type


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
