# pylint: disable=line-too-long

import collections.abc
import inspect
import io
import os
import re
import shutil
import socket
import subprocess  # nosec
import sys
import tarfile
import tempfile
import textwrap
import unittest

import parso
from bpc_utils import (
    LOOKUP_TABLE, PARSO_GRAMMAR_VERSIONS, BPCSyntaxError, Config, MakeTextIO, TaskLock,
    UUID4Generator, _mp_map_wrapper, archive_files, detect_encoding, detect_files,
    detect_indentation, detect_linesep, expand_glob_iter, first_non_none, first_truthy,
    get_parso_grammar_versions, is_python_filename, is_windows, map_tasks, parallel_available,
    parse_boolean_state, parse_indentation, parse_linesep, parso_parse, recover_files)


def read_text_file(filename, encoding='utf-8'):
    """Read text file."""
    with open(filename, 'r', encoding=encoding) as file:
        return file.read()


def write_text_file(filename, content, encoding='utf-8'):
    """Write text file."""
    with open(filename, 'w', encoding=encoding) as file:
        file.write(content)


def native_path(path):
    """Convert a file system path to the native form."""
    return path.replace('/', '\\') if is_windows else path


def square(x):
    return x ** 2


class SuccessCase:
    """A test case that expects a returned result."""
    def __init__(self, args=None, kwargs=None, result=None):
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.result = result

    def __repr__(self):  # pragma: no cover
        return 'SuccessCase(args={!r}, kwargs={!r}, result={!r})'.format(self.args, self.kwargs, self.result)


class FailCase:
    """A test case that expects an exception to be raised."""
    def __init__(self, args=None, kwargs=None, exc=BaseException, msg=''):
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.exc = exc
        self.msg = msg

    def __repr__(self):  # pragma: no cover
        return 'FailCase(args={!r}, kwargs={!r}, exc={!r}, msg={!r})'.format(self.args, self.kwargs, self.exc, self.msg)


class TestBPCUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_cwd = os.getcwd()
        cls.tmpd = tempfile.mkdtemp(prefix='bpc-utils-test-')
        os.chdir(cls.tmpd)

        write_text_file('README.md', 'rrr')
        write_text_file('a.py', 'aaa')
        write_text_file('b.PY', 'bbb')
        write_text_file('c.pyw', 'ccc')
        write_text_file('prefix1.py', 'pf1')
        write_text_file('prefix2.py', 'pf2')
        write_text_file('myscript', 'mmm')
        write_text_file('.hidden.py', 'hhh')
        os.mkdir('dir')
        write_text_file(os.path.join('dir', 'd.py'), 'ddd')
        write_text_file(os.path.join('dir', 'e.pyw'), 'eee')
        write_text_file(os.path.join('dir', 'config.json'), 'cfg')
        write_text_file(os.path.join('dir', 'apy'), 'apy')
        write_text_file(os.path.join('dir', 'bpy.py'), 'bpy')
        os.mkdir('fake.py')
        write_text_file(os.path.join('fake.py', 'f.py'), 'fff')
        os.mkdir('.hidden_dir')
        write_text_file(os.path.join('.hidden_dir', 'g.py'), 'ggg')

        # test symlink and hardlink on Unix-like platforms
        if not is_windows:  # pragma: no cover
            os.symlink('dir/apy', 'symlink1.py')
            os.symlink('dir/bpy.py', 'symlink2')
            os.symlink('loop2', 'loop1')
            os.symlink('loop1', 'loop2')
            os.symlink('..', '.hidden_dir/loopout')
            os.link('dir/d.py', 'hardlink.py')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpd, ignore_errors=True)
        os.chdir(cls.old_cwd)

    def setUp(self):
        self.success_cases = []
        self.fail_cases = []
        self.target_func = None
        self.assert_func = self.assertEqual

    def tearDown(self):
        shutil.rmtree('archive', ignore_errors=True)

    def generic_functional_test(self):
        for test_case in self.success_cases:
            with self.subTest(test_case=test_case):
                self.assert_func(self.target_func(*test_case.args, **test_case.kwargs), test_case.result)

        for test_case in self.fail_cases:
            with self.subTest(test_case=test_case):
                with self.assertRaisesRegex(test_case.exc, test_case.msg):
                    self.target_func(*test_case.args, **test_case.kwargs)

    def test_exports(self):
        self.assertTrue(issubclass(BPCSyntaxError, SyntaxError))
        with TaskLock():
            pass

    def test_parso_grammar_versions(self):
        self.assertIsInstance(PARSO_GRAMMAR_VERSIONS, list)
        self.assertIsInstance(PARSO_GRAMMAR_VERSIONS[0], tuple)
        versions1 = get_parso_grammar_versions()
        self.assertGreater(len(versions1), 0)
        self.assertIsInstance(versions1[0], str)
        self.assertIn('.', versions1[0])
        versions2 = get_parso_grammar_versions(minimum=versions1[1])
        self.assertEqual(len(versions1) - len(versions2), 1)
        with self.assertRaisesRegex(ValueError, 'invalid minimum version'):
            get_parso_grammar_versions(3.8)
        with self.assertRaisesRegex(ValueError, 'invalid minimum version'):
            get_parso_grammar_versions('x.y')

    def test_first_truthy(self):
        self.success_cases = [
            SuccessCase(args=(0, 1), result=1),
            SuccessCase(args=(1, 0), result=1),
            SuccessCase(args=([1],), result=1),
            SuccessCase(args=([0, [0]],), result=[0]),
            SuccessCase(args=([{0}, 0],), result={0}),
            SuccessCase(args=([],), result=None),
            SuccessCase(args=([''],), result=None),
            SuccessCase(args=([0, ()],), result=None),
            SuccessCase(args=(0, ()), result=None),
        ]
        self.fail_cases = [
            FailCase(args=(), exc=TypeError, msg='no arguments provided'),
            FailCase(args=(1,), exc=TypeError, msg='is not iterable'),
        ]
        self.target_func = first_truthy
        self.generic_functional_test()

    def test_first_non_none(self):
        self.success_cases = [
            SuccessCase(args=(0, 1), result=0),
            SuccessCase(args=(1, 0), result=1),
            SuccessCase(args=(None, 0), result=0),
            SuccessCase(args=(0, None), result=0),
            SuccessCase(args=([0],), result=0),
            SuccessCase(args=([None, 0],), result=0),
            SuccessCase(args=([0, None],), result=0),
            SuccessCase(args=([],), result=None),
            SuccessCase(args=([None],), result=None),
            SuccessCase(args=([None, None],), result=None),
            SuccessCase(args=(None, None), result=None),
        ]
        self.fail_cases = [
            FailCase(args=(), exc=TypeError, msg='no arguments provided'),
            FailCase(args=(1,), exc=TypeError, msg='is not iterable'),
        ]
        self.target_func = first_non_none
        self.generic_functional_test()

    def test_parse_boolean_state(self):
        self.success_cases = [
            SuccessCase(args=(None,), result=None),
            SuccessCase(args=('1',), result=True),
            SuccessCase(args=('yes',), result=True),
            SuccessCase(args=('Y',), result=True),
            SuccessCase(args=('True',), result=True),
            SuccessCase(args=('ON',), result=True),
            SuccessCase(args=('0',), result=False),
            SuccessCase(args=('NO',), result=False),
            SuccessCase(args=('n',), result=False),
            SuccessCase(args=('FALSE',), result=False),
            SuccessCase(args=('Off',), result=False),
        ]
        self.fail_cases = [
            FailCase(args=('',), exc=ValueError, msg="invalid boolean state value ''"),
            FailCase(args=('X',), exc=ValueError, msg="invalid boolean state value 'X'"),
        ]
        self.target_func = parse_boolean_state
        self.generic_functional_test()

    def test_parse_linesep(self):
        self.success_cases = [
            SuccessCase(args=(None,), result=None),
            SuccessCase(args=('',), result=None),
            SuccessCase(args=('\n',), result='\n'),
            SuccessCase(args=('\r\n',), result='\r\n'),
            SuccessCase(args=('\r',), result='\r'),
            SuccessCase(args=('LF',), result='\n'),
            SuccessCase(args=('CRLF',), result='\r\n'),
            SuccessCase(args=('cr',), result='\r'),
        ]
        self.fail_cases = [
            FailCase(args=('X',), exc=ValueError, msg="invalid linesep value 'X'"),
        ]
        self.target_func = parse_linesep
        self.generic_functional_test()

    def test_parse_indentation(self):
        self.success_cases = [
            SuccessCase(args=(None,), result=None),
            SuccessCase(args=('',), result=None),
            SuccessCase(args=('t',), result='\t'),
            SuccessCase(args=('T',), result='\t'),
            SuccessCase(args=('tab',), result='\t'),
            SuccessCase(args=('Tab',), result='\t'),
            SuccessCase(args=('TAB',), result='\t'),
            SuccessCase(args=('2',), result=' ' * 2),
            SuccessCase(args=('4',), result=' ' * 4),
            SuccessCase(args=('8',), result=' ' * 8),
        ]
        self.fail_cases = [
            FailCase(args=('X',), exc=ValueError, msg="invalid indentation value 'X'"),
            FailCase(args=('0',), exc=ValueError, msg="invalid indentation value '0'"),
            FailCase(args=('-1',), exc=ValueError, msg="invalid indentation value '-1'"),
            FailCase(args=('1.1',), exc=ValueError, msg="invalid indentation value '1.1'"),
        ]
        self.target_func = parse_indentation
        self.generic_functional_test()

    def test_uuid_gen(self):
        for dash in (True, False):
            with self.subTest(dash=dash):
                uuid_gen = UUID4Generator(dash=dash)
                uuids = [uuid_gen.gen() for _ in range(1000)]
                self.assertTrue(all(('-' in x) == dash for x in uuids))
                self.assertEqual(len(uuids), len(set(uuids)))

    def test_is_python_filename(self):
        self.success_cases = [
            SuccessCase(args=('a.py',), result=True),
            SuccessCase(args=('b.PY',), result=is_windows),
            SuccessCase(args=('c.pyw',), result=True),
            SuccessCase(args=('README.md',), result=False),
            SuccessCase(args=('myscript',), result=False),
            SuccessCase(args=('.hidden.py',), result=True),
        ]
        self.target_func = is_python_filename
        self.generic_functional_test()

    def test_expand_glob_iter(self):
        self.assertTrue(inspect.isgenerator(expand_glob_iter('*')))
        test_cases = [
            ('*', ['README.md', 'a.py', 'b.PY', 'c.pyw', 'prefix1.py', 'prefix2.py', 'myscript', 'dir', 'fake.py']),
            ('.*', ['.hidden.py', '.hidden_dir']),
            ('./.*', ['./.hidden.py', './.hidden_dir']),
            ('*.py', ['a.py', 'prefix1.py', 'prefix2.py', 'fake.py']),
            ('prefix*', ['prefix1.py', 'prefix2.py']),
        ]

        if is_windows:  # pragma: no cover
            test_cases[3][1].append('b.PY')
            test_cases.append(('./*', ['./' + p for p in test_cases[0][1]]))
            test_cases.append(('.\\*', test_cases[-1][1]))
        else:  # pragma: no cover
            test_cases[3][1].extend(['symlink1.py', 'hardlink.py'])
            test_cases[0][1].extend(['symlink1.py', 'symlink2', 'loop1', 'loop2', 'hardlink.py'])
            test_cases.append(('./*', ['./' + p for p in test_cases[0][1]]))

        if sys.version_info[:2] >= (3, 5):  # pragma: no cover
            test_cases.append(('./**/*.pyw', ['./c.pyw', './dir/e.pyw']))

        self.success_cases = [SuccessCase(args=(tc[0],), result=[native_path(p) for p in tc[1]]) for tc in test_cases]
        self.target_func = lambda pattern: list(expand_glob_iter(pattern))
        self.assert_func = self.assertCountEqual
        self.generic_functional_test()

    def test_detect_files(self):
        test_cases = [
            (['a.py'], ['a.py']),
            (['myscript'], ['myscript']),
            (['myscript', '.'], ['myscript', 'a.py', 'c.pyw', 'prefix1.py', 'prefix2.py', '.hidden.py', 'dir/d.py', 'dir/e.pyw', 'dir/bpy.py', 'fake.py/f.py', '.hidden_dir/g.py']),
        ]

        if is_windows:  # pragma: no cover
            test_cases[2][1].append('b.PY')
            test_cases.append((['*.py'], ['a.py', 'b.PY', 'prefix1.py', 'prefix2.py', 'fake.py/f.py']))
        else:  # pragma: no cover
            test_cases[2][1].append('dir/apy')
            test_cases.append((['*.py'], []))  # glob expansion should not be performed on Unix-like platforms

        self.success_cases = [SuccessCase(args=(tc[0],), result=[os.path.abspath(f) for f in tc[1]]) for tc in test_cases]
        self.target_func = detect_files
        self.assert_func = self.assertCountEqual
        self.generic_functional_test()

    def test_archive_and_restore(self):
        file_list = ['a.py', 'myscript', os.path.join('dir', 'e.pyw')]
        file_list = [os.path.abspath(p) for p in file_list]
        archive_file = archive_files(file_list, 'archive')
        with tarfile.open(archive_file, 'r') as tarf:
            items = tarf.getnames()
            self.assertEqual(len(items), 4)
            self.assertIn(LOOKUP_TABLE, items)
            self.assertEqual(sum(x.endswith('.py') for x in items), 3)
        write_text_file('a.py', '[redacted]')
        write_text_file(os.path.join('dir', 'e.pyw'), '[redacted]')
        recover_files(archive_file)
        self.assertEqual(read_text_file('a.py'), 'aaa')
        self.assertEqual(read_text_file(os.path.join('dir', 'e.pyw')), 'eee')

    def test_detect_encoding(self):
        self.success_cases = [
            SuccessCase(args=(b'# coding: gbk\n\xd6\xd0\xce\xc4',), result='gbk'),
            SuccessCase(args=(b'\xef\xbb\xbfhello',), result='utf-8-sig'),
            SuccessCase(args=(b'hello',), result='utf-8'),
        ]
        self.fail_cases = [
            FailCase(args=('hello',), exc=TypeError, msg="'code' should be bytes"),
        ]
        self.target_func = detect_encoding
        self.generic_functional_test()

    def test_MakeTextIO(self):
        # str
        with MakeTextIO('hello') as file:
            self.assertIsInstance(file, io.StringIO)
            self.assertEqual(file.read(), 'hello')
        self.assertTrue(file.closed)

        # seekable file
        with io.StringIO('deadbeef') as sio:
            self.assertTrue(sio.seekable())
            sio.seek(2)
            self.assertEqual(sio.read(2), 'ad')
            with MakeTextIO(sio) as file:
                self.assertEqual(file.read(), 'deadbeef')
            self.assertFalse(sio.closed)
            self.assertEqual(sio.tell(), 4)

        # unseekable file
        with socket.socket() as s:
            s.connect(('httpbin.org', 80))
            s.send(b'GET /anything HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n')
            with s.makefile() as file1:
                self.assertFalse(file1.seekable())
                with MakeTextIO(file1) as file2:
                    data = file2.read()
                    self.assertTrue(data.startswith('HTTP/1.1 200 OK'))

    def test_detect_linesep(self):
        test_cases = [
            ('1\n2\n3\n', '\n'),
            ('1\r2\r3\r', '\r'),
            ('1\r\n2\r\n3\r\n', '\r\n'),
            ('1\r2\r3\n', '\r'),
            ('1\n2\n3\r4\r', '\n'),
            ('1\n2\r\n3\r\n4\r5\r', '\r\n'),
            ('1\n2\n3\r4\v\r5\r\n6\r\n', '\n'),
        ]
        self.success_cases = [SuccessCase(args=(tc[0],), result=tc[1]) for tc in test_cases]
        self.success_cases += [SuccessCase(args=(tc[0].encode(),), result=tc[1]) for tc in test_cases]
        self.success_cases += [SuccessCase(args=(parso.parse(tc[0]),), result=tc[1]) for tc in test_cases]
        self.target_func = detect_linesep
        self.generic_functional_test()

        with io.StringIO(test_cases[-1][0], newline='') as file:
            self.assertEqual(detect_linesep(file), test_cases[-1][1])

        with socket.socket() as s:
            s.connect(('httpbin.org', 80))
            s.send(b'HEAD / HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n')
            with s.makefile(newline='') as file:
                self.assertEqual(detect_linesep(file), '\r\n')

    def test_detect_indentation(self):
        test_cases = [
            ('foo', '    '),
            ('for x in [1]:\n    pass', '    '),
            ('for x in [1]:\n  pass', '  '),
            ('for x in [1]:\n\tpass', '\t'),
            ('for x in [1]:\n\t  pass', '    '),
            ('for x in [1]:\n\tpass\nfor x in [1]:\n    pass', '    '),
            ('for x in [1]:\n    pass\nfor x in [1]:\n  pass', '  '),
        ]
        self.success_cases = [SuccessCase(args=(tc[0],), result=tc[1]) for tc in test_cases]
        self.success_cases += [SuccessCase(args=(tc[0].encode(),), result=tc[1]) for tc in test_cases]
        self.success_cases += [SuccessCase(args=(parso.parse(tc[0]),), result=tc[1]) for tc in test_cases]
        self.target_func = detect_indentation
        self.generic_functional_test()

        with io.StringIO(test_cases[-1][0], newline='') as file:
            self.assertEqual(detect_indentation(file), test_cases[-1][1])

    def test_mixed_linesep_and_indentation(self):
        test_case = ('for x in [1]:\n    pass\rfor x in [1]:\r  pass', '\r', '  ')
        self.assertEqual(detect_linesep(test_case[0]), test_case[1])
        self.assertEqual(detect_indentation(test_case[0]), test_case[2])
        with io.StringIO(test_case[0], newline='') as file:
            self.assertEqual(detect_linesep(file), test_case[1])
            self.assertEqual(detect_indentation(file), test_case[2])

    def test_parso_parse(self):
        parso_parse('1+1')
        parso_parse(b'1+1')
        parso_parse('1@1', version='3.5')
        parso_parse(b'# coding: gbk\n\xd6\xd0\xce\xc4')
        self.fail_cases = [
            FailCase(args=('1@1',), kwargs={'version': '3.4'}, exc=BPCSyntaxError, msg="source file '<unknown>' contains the following syntax errors"),
            FailCase(args=('1@1',), kwargs={'version': '3.4', 'filename': 'temp'}, exc=BPCSyntaxError, msg="source file 'temp' contains the following syntax errors"),
            FailCase(args=('1@1',), kwargs={'version': '3.4', 'filename': ''}, exc=BPCSyntaxError, msg="source file '' contains the following syntax errors"),
            FailCase(args=('1@1',), kwargs={'version': ''}, exc=ValueError, msg='The given version is not in the right format.'),
        ]
        self.target_func = parso_parse
        self.generic_functional_test()

    def test__mp_map_wrapper(self):
        self.success_cases = [
            SuccessCase(args=((square, (6,), {}),), result=36),
            SuccessCase(args=((square, range(6, 7), {}),), result=36),  # pylint: disable=range-builtin-not-iterating
            SuccessCase(args=((int, ('0x10',), {'base': 16}),), result=16),
            SuccessCase(args=((int, ('0x10',), Config(base=16)),), result=16),
        ]
        self.target_func = _mp_map_wrapper
        self.generic_functional_test()

    def test_map_tasks(self):
        test_cases = [
            (square, [1, 2, 3], None, None, [1, 4, 9]),
            (square, range(1, 4), None, None, [1, 4, 9]),  # pylint: disable=range-builtin-not-iterating
            (divmod, [4, 7, 9], (3,), None, [(1, 1), (2, 1), (3, 0)]),
            (int, ['0x%c' % c for c in 'abc'], None, {'base': 0}, [10, 11, 12]),
            (max, [4, -7, 9], range(6, 7), Config(key=abs), [6, -7, 9]),  # pylint: disable=range-builtin-not-iterating
        ]
        self.success_cases = []
        for tc in test_cases:
            for processes in (None, 1, 2):
                for chunksize in (None, 2):
                    self.success_cases.append(SuccessCase(args=(tc[0], tc[1]), kwargs={
                        'posargs': tc[2],
                        'kwargs': tc[3],
                        'processes': processes,
                        'chunksize': chunksize,
                    }, result=tc[4]))
        self.target_func = map_tasks

        # test under normal condition
        self.generic_functional_test()

        # test when parallel execution is not available
        parallel_available_old = sys.modules['bpc_utils'].parallel_available
        sys.modules['bpc_utils'].parallel_available = False
        self.generic_functional_test()
        sys.modules['bpc_utils'].parallel_available = parallel_available_old

    def test_lock(self):
        num_tasks = 10
        num_print = 1000
        code_template = textwrap.dedent("""\
            from bpc_utils import TaskLock, map_tasks


            def task(task_id):
                {context}
                    for i in range({num_print}):
                        print('Task %d says %d' % (task_id, i), flush=True)


            if __name__ == '__main__':
                map_tasks(task, range({num_tasks}))
        """)
        code_no_lock = code_template.format(context='for _ in [0]:', num_print=num_print, num_tasks=num_tasks)
        code_with_lock = code_template.format(context='with TaskLock():', num_print=num_print, num_tasks=num_tasks)

        def has_interleave(output):
            records = re.findall(r'Task (\d+) says (\d+)', output)
            task_events = [[] for _ in range(num_tasks)]
            for i, r in enumerate(records):
                task_events[int(r[0])].append((i, int(r[1])))
            for i in range(num_tasks):
                if [ev[1] for ev in task_events[i]] != list(range(num_print)):  # pragma: no cover
                    raise ValueError('task %d prints incorrectly' % i)
            for i in range(num_tasks):
                start = task_events[i][0][0]
                if [ev[0] for ev in task_events[i]] != list(range(start, start + num_print)):
                    return True
            return False

        shutil.copy(sys.modules['bpc_utils'].__file__, '.')
        test_filename = 'test-lock.py'

        write_text_file(test_filename, code_no_lock)
        output = subprocess.check_output([sys.executable, '-u', test_filename]).decode()  # nosec
        self.assertEqual(has_interleave(output), parallel_available)

        write_text_file(test_filename, code_with_lock)
        output = subprocess.check_output([sys.executable, '-u', test_filename]).decode()  # nosec
        self.assertFalse(has_interleave(output))

    def test_Config(self):
        config = Config(foo='var', bar=True, boo=1)
        self.assertIsInstance(config, collections.abc.MutableMapping)
        self.assertEqual(config.foo, 'var')  # pylint: disable=no-member
        self.assertEqual(config.bar, True)  # pylint: disable=no-member
        self.assertEqual(config.boo, 1)  # pylint: disable=no-member
        self.assertEqual(config['foo'], 'var')
        self.assertEqual(config['bar'], True)
        self.assertEqual(config['boo'], 1)
        self.assertTrue('foo' in config)
        self.assertFalse('moo' in config)
        self.assertFalse('666' in config)
        self.assertEqual(len(config), 3)
        self.assertEqual(repr(config), "Config(bar=True, boo=1, foo='var')")

        config['666'] = '777'
        self.assertTrue('666' in config)
        self.assertEqual(config['666'], '777')

        setattr(config, '666', '888')
        self.assertEqual(config['666'], '888')

        del config['666']
        self.assertFalse('666' in config)

        delattr(config, 'foo')
        self.assertFalse('foo' in config)

        del config.bar  # pylint: disable=no-member
        self.assertFalse('bar' in config)
        self.assertEqual(len(config), 1)
        for key, value in config.items():
            self.assertEqual(key, 'boo')
            self.assertEqual(value, 1)

        config.xxx = 'yyy'
        self.assertTrue('xxx' in config)
        self.assertEqual(config['xxx'], 'yyy')

        self.assertEqual(dict(Config(a=1, b=2)), {'a': 1, 'b': 2})
        self.assertEqual(Config(a=1, b=2), Config(b=2, a=1))
        self.assertNotEqual(Config(a=1, b=2), {'a': 1, 'b': 2})
        self.assertNotEqual(Config(a=1, b=2), Config(b=1, a=2))

        self.assertEqual(repr(Config(**{'z': 1, 'y': '2'})), "Config(y='2', z=1)")
        self.assertEqual(repr(Config(**{'z': True, '@': []})), "Config(z=True, **{'@': []})")
        self.assertEqual(repr(Config(**{'z': (), '8': 2})), "Config(z=(), **{'8': 2})")
        self.assertEqual(repr(Config(zz='zoo', **{'z': 1, 'return': 2})), "Config(z=1, zz='zoo', **{'return': 2})")
        self.assertEqual(repr(Config(**{'z': 1, '__debug__': {}})), "Config(z=1, **{'__debug__': {}})")
        self.assertEqual(repr(Config(**{'return': 0})), "Config(**{'return': 0})")
        if sys.version_info[:2] >= (3, 6):  # dict preserves insertion order  # pragma: no cover
            self.assertEqual(repr(Config(**{'z': 1, 'return': 2, '8': 3})), "Config(z=1, **{'8': 3, 'return': 2})")
            self.assertEqual(repr(Config(**{'return': 0, '8': 3})), "Config(**{'8': 3, 'return': 0})")


if __name__ == '__main__':
    unittest.main()
