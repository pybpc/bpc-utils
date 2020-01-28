import os
import shutil
import sys
import tarfile
import tempfile
import unittest

import parso
from bpc_utils import (LOOKUP_TABLE, PARSO_GRAMMAR_VERSIONS, ConvertError, UUID4Generator,
                       archive_files, detect_encoding, detect_files, detect_indentation,
                       detect_linesep, expand_glob, get_parso_grammar_versions, is_python_filename,
                       is_windows, parso_parse, recover_files)


def read_text_file(filename, encoding='utf-8'):
    """Read text file."""
    with open(filename, 'r', encoding=encoding) as file:
        return file.read()


def write_text_file(filename, content, encoding='utf-8'):
    """Write text file."""
    with open(filename, 'w', encoding=encoding) as file:
        file.write(content)


def native_path(path):
    return path.replace('/', '\\') if is_windows else path


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

    def tearDown(self):
        shutil.rmtree('archive', ignore_errors=True)

    def test_parso_grammar_versions(self):
        self.assertIsInstance(PARSO_GRAMMAR_VERSIONS, list)
        self.assertIsInstance(PARSO_GRAMMAR_VERSIONS[0], tuple)
        versions1 = get_parso_grammar_versions()
        self.assertGreater(len(versions1), 0)
        self.assertIsInstance(versions1[0], str)
        self.assertIn('.', versions1[0])
        versions2 = get_parso_grammar_versions(minimum=versions1[1])
        self.assertEqual(len(versions1) - len(versions2), 1)

    def test_uuid_gen(self):
        for dash in (True, False):
            with self.subTest(dash=dash):
                uuid_gen = UUID4Generator(dash=dash)
                uuids = [uuid_gen.gen() for _ in range(1000)]
                self.assertTrue(all(('-' in x) == dash for x in uuids))
                self.assertEqual(len(uuids), len(set(uuids)))

    def test_is_python_filename(self):
        test_cases = [
            ('a.py', True),
            ('b.PY', is_windows),
            ('c.pyw', True),
            ('README.md', False),
            ('myscript', False),
            ('.hidden.py', True),
        ]

        for test_case in test_cases:
            filename, expected_result = test_case
            with self.subTest(test_case=test_case):
                self.assertEqual(is_python_filename(filename), expected_result)

    def test_expand_glob(self):
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

        for test_case in test_cases:
            pattern, expected_result = test_case
            with self.subTest(test_case=test_case):
                self.assertCountEqual(expand_glob(pattern), [native_path(p) for p in expected_result])

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

        for test_case in test_cases:
            infiles, outfiles = test_case
            with self.subTest(test_case=test_case):
                self.assertCountEqual(detect_files(infiles), [os.path.abspath(f) for f in outfiles])

    def test_archive_and_restore(self):
        file_list = ['a.py', 'myscript', os.path.join('dir', 'e.pyw')]
        file_list = [os.path.abspath(p) for p in file_list]
        archive_files(file_list, 'archive')
        archive_file = os.path.join('archive', os.listdir('archive')[0])
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
        test_cases = [
            (b'# coding: gbk\n\xd6\xd0\xce\xc4', 'gbk'),
            (b'\xef\xbb\xbfhello', 'utf-8-sig'),
            (b'hello', 'utf-8'),
        ]

        for test_case in test_cases:
            code, encoding = test_case
            with self.subTest(test_case=test_case):
                self.assertEqual(detect_encoding(code), encoding)

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

        test_cases += [(tc[0].encode(), tc[1]) for tc in test_cases] + [(parso.parse(tc[0]), tc[1]) for tc in test_cases]

        for test_case in test_cases:
            code, linesep = test_case
            with self.subTest(test_case=test_case):
                self.assertEqual(detect_linesep(code), linesep)

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

        test_cases += [(tc[0].encode(), tc[1]) for tc in test_cases] + [(parso.parse(tc[0]), tc[1]) for tc in test_cases]

        for test_case in test_cases:
            code, indentation = test_case
            with self.subTest(test_case=test_case):
                self.assertEqual(detect_indentation(code), indentation)

    def test_parso_parse(self):
        parso_parse('1+1')
        parso_parse(b'1+1')
        parso_parse('1@1', version='3.5')
        parso_parse(b'# coding: gbk\n\xd6\xd0\xce\xc4')
        parso_parse(b'\xd6\xd0\xce\xc4', encoding='gbk', errors='strict')
        with self.assertRaisesRegex(ConvertError, "source file '<unknown>' contains the following syntax errors"):
            parso_parse('1@1', version='3.4')
        with self.assertRaisesRegex(ConvertError, "source file 'temp' contains the following syntax errors"):
            parso_parse('1@1', version='3.4', file='temp')


if __name__ == '__main__':
    unittest.main()