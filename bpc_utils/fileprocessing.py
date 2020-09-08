"""File processing routines for BPC."""

import binascii
import collections
import contextlib
import glob
import itertools
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time

from .misc import UUID4Generator, is_windows
from .typing import Deque, Dict, Final, Iterable, Iterator, List, Set, Tuple

# gzip support detection
try:
    import zlib  # pylint: disable=unused-import # noqa: F401
    import gzip
    gzip.GzipFile  # pylint: disable=pointless-statement
except (ImportError, AttributeError):  # pragma: no cover
    has_gz_support = False
else:
    has_gz_support = True

#: Final[str]: File name for the lookup table in the archive file.
LOOKUP_TABLE = '_lookup_table.json'  # type: Final[str]


def is_python_filename(filename: str) -> bool:
    """Determine whether a file is a Python source file by its extension.

    Args:
        filename: the name of the file

    Returns:
        whether the file is a Python source file

    """
    if is_windows:  # pragma: no cover
        filename = filename.lower()
    return os.path.splitext(filename)[1] in {'.py', '.pyw'}


def expand_glob_iter(pattern: str) -> Iterator[str]:
    """Wrapper function to perform glob expansion.

    Args:
        pattern: the pattern to expand

    Returns:
        an iterator of expansion result

    """
    if sys.version_info[:2] < (3, 5):  # pragma: no branch
        return glob.iglob(pattern)  # pragma: no cover
    return glob.iglob(pattern, recursive=True)  # pragma: no cover  # novermin


def detect_files(files: Iterable[str]) -> List[str]:
    """Get a list of Python files to be processed according to user input.

    This will perform *glob* expansion on Windows, make all paths absolute,
    resolve symbolic links and remove duplicates.

    Args:
        files: a list of files and directories to process (usually provided by users on command-line)

    Returns:
        a list of Python files to be processed

    See Also:
        See :func:`~bpc_utils.fileprocessing.expand_glob_iter` for more information.

    """
    file_list = []  # type: List[str]
    directory_queue = collections.deque()  # type: Deque[str]
    directory_visited = set()  # type: Set[str]

    # perform glob expansion on windows
    if is_windows:  # pragma: no cover
        files = itertools.chain.from_iterable(map(expand_glob_iter, files))

    # find top-level files and directories
    for file in files:
        file = os.path.realpath(file)
        if os.path.isfile(file):  # user specified files should be added even without .py extension
            file_list.append(file)
        elif os.path.isdir(file):
            directory_queue.appendleft(file)
            directory_visited.add(file)

    # find files in subdirectories
    while directory_queue:
        directory = directory_queue.pop()
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            item_realpath = os.path.realpath(item_path)
            if os.path.isfile(item_realpath) and (is_python_filename(item_path) or is_python_filename(item_realpath)):
                file_list.append(item_realpath)
            elif os.path.isdir(item_realpath):
                if item_realpath not in directory_visited:  # avoid symlink directory loops
                    directory_queue.appendleft(item_realpath)
                    directory_visited.add(item_realpath)

    # remove duplicates (including hard links pointing to the same file)
    file_dict = {}  # type: Dict[Tuple[int, int], str]
    for file in file_list:
        file_stat = os.stat(file)
        file_dict[(file_stat.st_ino, file_stat.st_dev)] = file
    return list(file_dict.values())


def archive_files(files: Iterable[str], archive_dir: str) -> str:
    """Archive the list of files into a *tar* file.

    Args:
        files: a list of files to be archived (should be *absolute path*)
        archive_dir: the directory to save the archive

    Returns:
        path to the generated *tar* archive

    """
    uuid_gen = UUID4Generator()
    lookup_table = {uuid_gen.gen() + '.py': file for file in files}  # type: Dict[str, str]
    random_string = binascii.hexlify(os.urandom(8)).decode('ascii')
    archive_file = 'archive-{}-{}.tar'.format(time.strftime('%Y%m%d%H%M%S'), random_string)
    archive_mode = 'w'
    if has_gz_support:  # pragma: no cover
        archive_file += '.gz'
        archive_mode += ':gz'
    archive_file = os.path.join(archive_dir, archive_file)
    os.makedirs(archive_dir, exist_ok=True)
    with tarfile.open(archive_file, archive_mode) as tarf:
        for arcname, realname in lookup_table.items():
            tarf.add(realname, arcname)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', prefix='bpc-archive-lookup-',
                                         suffix='.json', delete=False) as tmpf:
            json.dump(lookup_table, tmpf, indent=4)
        tarf.add(tmpf.name, LOOKUP_TABLE)
        with contextlib.suppress(OSError):
            os.remove(tmpf.name)
    return archive_file


def recover_files(archive_file: str) -> None:
    """Recover files from a *tar* archive.

    Args:
        archive_file: path to the *tar* archive file

    """
    with tarfile.open(archive_file, 'r') as tarf:
        with tempfile.TemporaryDirectory(prefix='bpc-archive-extract-') as tmpd:
            tarf.extractall(tmpd)
            with open(os.path.join(tmpd, LOOKUP_TABLE)) as lookupf:
                lookup_table = json.load(lookupf)  # type: Dict[str, str]
            for arcname, realname in lookup_table.items():
                os.makedirs(os.path.dirname(realname), exist_ok=True)
                shutil.move(os.path.join(tmpd, arcname), realname)


__all__ = ['detect_files', 'archive_files', 'recover_files']
