import collections.abc
import io
import socket
import sys

import pytest
from bpc_utils import Config, UUID4Generator, first_non_none, first_truthy
from bpc_utils.misc import MakeTextIO


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
def test_first_truthy(args, result):
    assert first_truthy(*args) == result  # nosec


@pytest.mark.parametrize(
    'args,exc,msg',
    [
        ((), TypeError, 'no arguments provided'),
        ((1,), TypeError, 'is not iterable'),
    ]
)
def test_first_truthy_error(args, exc, msg):
    with pytest.raises(exc, match=msg):
        first_truthy(*args)


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
def test_first_non_none(args, result):
    assert first_non_none(*args) == result  # nosec


@pytest.mark.parametrize(
    'args,exc,msg',
    [
        ((), TypeError, 'no arguments provided'),
        ((1,), TypeError, 'is not iterable'),
    ]
)
def test_first_non_none_error(args, exc, msg):
    with pytest.raises(exc, match=msg):
        first_non_none(*args)


@pytest.mark.parametrize('dash', [True, False])
def test_uuid_gen(dash):
    uuid_gen = UUID4Generator(dash=dash)
    uuids = [uuid_gen.gen() for _ in range(1000)]
    assert all(('-' in x) == dash for x in uuids)  # nosec
    assert len(uuids) == len(set(uuids))  # nosec


def test_MakeTextIO_str():
    with MakeTextIO('hello') as file:
        assert isinstance(file, io.StringIO)  # nosec
        assert file.read() == 'hello'  # nosec
    assert file.closed  # nosec


def test_MakeTextIO_seekable_file():
    with io.StringIO('deadbeef') as sio:
        assert sio.seekable()  # nosec
        sio.seek(2)
        assert sio.read(2) == 'ad'  # nosec
        with MakeTextIO(sio) as file:
            assert file.read() == 'deadbeef'  # nosec
        assert not sio.closed  # nosec
        assert sio.tell() == 4  # nosec


def test_MakeTextIO_unseekable_file():
    with socket.socket() as s:
        s.connect(('httpbin.org', 80))
        s.send(b'GET /anything HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n')
        with s.makefile() as file1:
            assert not file1.seekable()  # nosec
            with MakeTextIO(file1) as file2:
                data = file2.read()
                assert data.startswith('HTTP/1.1 200 OK')  # nosec


def test_Config():
    config = Config(foo='var', bar=True, boo=1)
    assert isinstance(config, collections.abc.MutableMapping)  # nosec
    assert config.foo == 'var'  # pylint: disable=no-member  # nosec
    assert config.bar is True  # pylint: disable=no-member  # nosec
    assert config.boo == 1  # pylint: disable=no-member  # nosec
    assert config['foo'] == 'var'  # nosec
    assert config['bar'] is True  # nosec
    assert config['boo'] == 1  # nosec
    assert 'foo' in config  # nosec
    assert 'moo' not in config  # nosec
    assert '666' not in config  # nosec
    assert len(config) == 3  # nosec
    assert repr(config) == "Config(bar=True, boo=1, foo='var')"  # nosec

    config['666'] = '777'
    assert '666' in config  # nosec
    assert config['666'] == '777'  # nosec

    setattr(config, '666', '888')
    assert config['666'] == '888'  # nosec

    del config['666']
    assert '666' not in config  # nosec

    delattr(config, 'foo')
    assert 'foo' not in config  # nosec

    del config.bar  # pylint: disable=no-member
    assert 'bar' not in config  # nosec
    assert len(config) == 1  # nosec
    for key, value in config.items():
        assert key == 'boo'  # nosec
        assert value == 1  # nosec

    config.xxx = 'yyy'
    assert 'xxx' in config  # nosec
    assert config['xxx'] == 'yyy'  # nosec

    assert dict(Config(a=1, b=2)) == {'a': 1, 'b': 2}  # nosec
    assert Config(a=1, b=2) == Config(b=2, a=1)  # nosec
    assert Config(a=1, b=2) != {'a': 1, 'b': 2}  # nosec
    assert Config(a=1, b=2) != Config(b=1, a=2)  # nosec

    assert repr(Config(**{'z': 1, 'y': '2'})) == "Config(y='2', z=1)"  # nosec
    assert repr(Config(**{'z': True, '@': []})) == "Config(z=True, **{'@': []})"  # nosec
    assert repr(Config(**{'z': (), '8': 2})) == "Config(z=(), **{'8': 2})"  # nosec
    assert repr(Config(zz='zoo', **{'z': 1, 'return': 2})) == "Config(z=1, zz='zoo', **{'return': 2})"  # nosec
    assert repr(Config(**{'z': 1, '__debug__': {}})) == "Config(z=1, **{'__debug__': {}})"  # nosec
    assert repr(Config(**{'return': 0})) == "Config(**{'return': 0})"  # nosec
    if sys.version_info[:2] >= (3, 6):  # dict preserves insertion order  # pragma: no cover
        assert repr(Config(**{'z': 1, 'return': 2, '8': 3})) == "Config(z=1, **{'8': 3, 'return': 2})"  # nosec
        assert repr(Config(**{'return': 0, '8': 3})) == "Config(**{'8': 3, 'return': 0})"  # nosec
