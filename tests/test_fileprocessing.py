import inspect
import os
import re
import sys
import tarfile
from pathlib import Path

import pytest
from bpc_utils import BPCRecoveryError, archive_files, detect_files, recover_files
from bpc_utils.fileprocessing import LOOKUP_TABLE, expand_glob_iter, is_python_filename
from bpc_utils.misc import is_windows
from bpc_utils.typing import List, Tuple

from .testutils import MonkeyPatch, TempPathFactory, read_text_file, write_text_file


def native_path(path: str) -> str:
    """Convert a file system path to the native form."""
    return path.replace('/', '\\') if is_windows else path


@pytest.fixture(scope='class')
def setup_files_for_tests(tmp_path_factory: TempPathFactory, monkeypatch_class: MonkeyPatch) -> None:
    tmp_path = tmp_path_factory.mktemp('bpc-utils-tests-')
    monkeypatch_class.chdir(tmp_path)
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


@pytest.mark.parametrize(
    'filename,result',
    [
        ('a.py', True),
        ('b.PY', is_windows),
        ('c.pyw', True),
        ('README.md', False),
        ('myscript', False),
        ('.hidden.py', True),
    ]
)
def test_is_python_filename(filename: str, result: bool) -> None:
    assert is_python_filename(filename) == result  # nosec


def test_expand_glob_iter_is_generator() -> None:
    assert inspect.isgenerator(expand_glob_iter('*'))  # nosec


def test_BPCRecoveryError() -> None:
    assert issubclass(BPCRecoveryError, RuntimeError)  # nosec


@pytest.mark.usefixtures('setup_files_for_tests')
class TestFileProcessingReadOnly:
    expand_glob_iter_test_cases = [
        ('*', ['README.md', 'a.py', 'b.PY', 'c.pyw', 'prefix1.py', 'prefix2.py', 'myscript', 'dir', 'fake.py']),
        ('.*', ['.hidden.py', '.hidden_dir']),
        ('./.*', ['./.hidden.py', './.hidden_dir']),
        ('*.py', ['a.py', 'prefix1.py', 'prefix2.py', 'fake.py']),
        ('prefix*', ['prefix1.py', 'prefix2.py']),
    ]  # type: List[Tuple[str, List[str]]]

    if is_windows:  # pragma: no cover
        expand_glob_iter_test_cases[3][1].append('b.PY')
        expand_glob_iter_test_cases.append(('./*', ['./' + p for p in expand_glob_iter_test_cases[0][1]]))
        expand_glob_iter_test_cases.append(('.\\*', expand_glob_iter_test_cases[-1][1]))
    else:  # pragma: no cover
        expand_glob_iter_test_cases[3][1].extend(['symlink1.py', 'hardlink.py'])
        expand_glob_iter_test_cases[0][1].extend(['symlink1.py', 'symlink2', 'loop1', 'loop2', 'hardlink.py'])
        expand_glob_iter_test_cases.append(('./*', ['./' + p for p in expand_glob_iter_test_cases[0][1]]))

    if sys.version_info[:2] >= (3, 5):  # pragma: no cover
        expand_glob_iter_test_cases.append(('./**/*.pyw', ['./c.pyw', './dir/e.pyw']))

    @pytest.mark.parametrize('pattern,result', expand_glob_iter_test_cases)
    def test_expand_glob_iter(self, pattern: str, result: List[str]) -> None:  # pylint: disable=no-self-use
        assert sorted(expand_glob_iter(pattern)) == sorted(map(native_path, result))  # nosec

    detect_files_test_cases = [
        (['a.py'], ['a.py']),
        (['myscript'], ['myscript']),
        (['myscript', '.'], ['myscript', 'a.py', 'c.pyw', 'prefix1.py', 'prefix2.py', '.hidden.py', 'dir/d.py',
                             'dir/e.pyw', 'dir/bpy.py', 'fake.py/f.py', '.hidden_dir/g.py']),
    ]  # type: List[Tuple[List[str], List[str]]]

    if is_windows:  # pragma: no cover
        detect_files_test_cases[2][1].append('b.PY')
        detect_files_test_cases.append((['*.py'], ['a.py', 'b.PY', 'prefix1.py', 'prefix2.py', 'fake.py/f.py']))
    else:  # pragma: no cover
        detect_files_test_cases[2][1].append('dir/apy')
        detect_files_test_cases.append((['*.py'], []))  # glob expansion should not be performed on Unix-like platforms

    @pytest.mark.parametrize('files,result', detect_files_test_cases)
    def test_detect_files(self, files: List[str], result: List[str]) -> None:  # pylint: disable=no-self-use
        assert sorted(detect_files(files)) == sorted(map(os.path.abspath, result))  # type: ignore[arg-type]  # nosec


@pytest.mark.parametrize(
    'rr,rs',
    [
        (False, False),
        (True, False),
        (False, True),
    ]
)
@pytest.mark.usefixtures('setup_files_for_tests')
def test_archive_and_restore(rr: bool, rs: bool) -> None:
    file_list = ['a.py', 'myscript', os.path.join('dir', 'e.pyw')]  # type: List[str]
    file_list = [os.path.abspath(p) for p in file_list]
    archive_dir = 'archive'
    archive_file = archive_files(file_list, archive_dir)
    with tarfile.open(archive_file, 'r') as tarf:
        items = tarf.getnames()
        assert len(items) == 4  # nosec
        assert LOOKUP_TABLE in items  # nosec
        assert sum(x.endswith('.py') for x in items) == 3  # nosec
    write_text_file('a.py', '[redacted]')
    write_text_file(os.path.join('dir', 'e.pyw'), '[redacted]')
    assert not (rr and rs)  # nosec
    recover_files(archive_dir if rs else archive_file, rr=rr, rs=rs)
    assert read_text_file('a.py') == 'aaa'  # nosec
    assert read_text_file(os.path.join('dir', 'e.pyw')) == 'eee'  # nosec
    if rs:
        assert not os.path.exists(archive_dir)  # nosec
        assert not os.path.exists(archive_file)  # nosec
    elif rr:
        assert not os.path.exists(archive_file)  # nosec
        assert os.path.isdir(archive_dir)  # nosec
    else:
        assert os.path.isdir(archive_dir)  # nosec
        assert os.path.isfile(archive_file)  # nosec


def test_recover_files_both_rr_rs() -> None:
    with pytest.raises(ValueError, match=re.escape("cannot use 'rr' and 'rs' at the same time")):
        recover_files(os.devnull, rr=True, rs=True)


def test_recover_files_rs_errors(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(BPCRecoveryError, match=re.escape("no archive files found in '.'")):
        recover_files('.', rs=True)
    Path('dir').mkdir()
    Path('file').touch()
    with pytest.raises(BPCRecoveryError, match=re.escape("more than one item found in '.'")):
        recover_files('.', rs=True)
    Path('file').unlink()
    with pytest.raises(BPCRecoveryError, match=re.escape("item 'dir' in '.' is not a regular file")):
        recover_files('.', rs=True)
