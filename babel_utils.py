import collections
import glob
import itertools
import json
import locale
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import time
import uuid

is_windows = platform.system() == 'Windows'

# gzip support detection
try:
    import zlib  # pylint: disable=unused-import
    import gzip
    gzip.GzipFile  # pylint: disable=pointless-statement
except (ImportError, AttributeError):  # pragma: no cover
    has_gz_support = False
else:
    has_gz_support = True

# multiprocessing support detection and CPU_CNT retrieval
try:        # try first
    import multiprocessing
except ImportError:  # pragma: no cover
    multiprocessing = None
else:       # CPU number if multiprocessing supported
    if os.name == 'posix' and 'SC_NPROCESSORS_CONF' in os.sysconf_names:  # pragma: no cover
        CPU_CNT = os.sysconf('SC_NPROCESSORS_CONF')
    elif 'sched_getaffinity' in os.__all__:  # pragma: no cover
        CPU_CNT = len(os.sched_getaffinity(0))  # novermin
    elif 'cpu_count' in os.__all__:  # pragma: no cover
        CPU_CNT = os.cpu_count() or 1  # novermin
    else:  # pragma: no cover
        CPU_CNT = 1
finally:    # alias and aftermath
    mp = multiprocessing
    del multiprocessing

# from configparser
BOOLEAN_STATES = {'1': True, '0': False,
                  'yes': True, 'no': False,
                  'true': True, 'false': False,
                  'on': True, 'off': False}

LOCALE_ENCODING = locale.getpreferredencoding(False)

LOOKUP_TABLE = '_lookup_table.json'


class UUID4Generator:
    """UUID 4 generator wrapper to prevent UUID collisions."""

    def __init__(self, dash=True):
        """Constructor of UUID 4 generator wrapper.

        Args:
            - `dash` -- `bool`, whether the generated UUID string has dashes or not

        """
        self.used_uuids = set()
        self.dash = dash

    def gen(self):
        """Generate a new UUID 4 string that is guaranteed not to collide with used UUIDs.

        Returns:
            - `str` -- a new UUID 4 string

        """
        while True:
            nuid = uuid.uuid4()
            nuid = str(nuid) if self.dash else nuid.hex
            if nuid not in self.used_uuids:  # pragma: no cover
                break
        self.used_uuids.add(nuid)
        return nuid


def is_python_filename(filename):
    """Determine whether a file is a Python source file by its extension.

    Args:
        - `filename` -- `str`, the name of the file

    Returns:
        - `bool` -- whether the file is a Python source file

    """
    if is_windows:  # pragma: no cover
        filename = filename.lower()
    return os.path.splitext(filename)[1] in ('.py', '.pyw')


def expand_glob(pathname):
    """Wrapper function to perform glob expansion.

    Args:
        - `pathname` -- `str`, the glob pattern

    Returns:
        - `List[str]` -- result of glob expansion

    """
    if sys.version_info[:2] < (3, 5):  # pragma: no cover
        return glob.glob(pathname)
    return glob.glob(pathname, recursive=True)  # novermin


def detect_files(files):
    """Get a list of Python files to be processed according to user input.
       This will perform glob expansion on Windows, make all paths absolute, resolve symbolic links and remove duplicates.

    Args:
        - `files` -- `List[str]`, a list of files and directories to process (usually provided by users on command-line)

    Returns:
        - `List[str]` -- a list of Python files to be processed

    """
    file_list = []
    directory_queue = collections.deque()
    directory_visited = set()

    # perform glob expansion on windows
    if is_windows:  # pragma: no cover
        files = itertools.chain(*map(expand_glob, files))

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
    file_dict = {}
    for file in file_list:
        file_stat = os.stat(file)
        file_dict[(file_stat.st_ino, file_stat.st_dev)] = file
    return list(file_dict.values())


def archive_files(files, archive_dir):
    """Archive the list of files into a tar file.

    Args:
        - `files` -- `List[str]`, a list of files to be archived (should be absolute path)
        - `archive_dir` -- `os.PathLike`, the directory to save the archive

    """
    uuid_gen = UUID4Generator()
    lookup_table = {uuid_gen.gen() + '.py': file for file in files}
    archive_file = 'archive-{}-{}.tar'.format(time.strftime('%Y%m%d%H%M%S'), os.urandom(8).hex())
    archive_mode = 'w'
    if has_gz_support:  # pragma: no cover
        archive_file += '.gz'
        archive_mode += ':gz'
    os.makedirs(archive_dir, exist_ok=True)
    with tarfile.open(os.path.join(archive_dir, archive_file), archive_mode) as tarf:
        for arcname, realname in lookup_table.items():
            tarf.add(realname, arcname)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', prefix='babel-archive-lookup-', suffix='.json', delete=False) as tmpf:
            json.dump(lookup_table, tmpf, indent=4)
        tarf.add(tmpf.name, LOOKUP_TABLE)
        try:
            os.remove(tmpf.name)
        except OSError:  # pragma: no cover
            pass


def recover_files(archive_file):
    """Recover files from a tar archive.

    Args:
        - `archive_file` -- `os.PathLike`, the name of the tar archive file

    """
    with tarfile.open(archive_file, 'r') as tarf:
        with tempfile.TemporaryDirectory(prefix='babel-archive-extract-') as tmpd:
            tarf.extractall(tmpd)
            with open(os.path.join(tmpd, LOOKUP_TABLE)) as lookupf:
                lookup_table = json.load(lookupf)
            for arcname, realname in lookup_table.items():
                os.makedirs(os.path.dirname(realname), exist_ok=True)
                shutil.move(os.path.join(tmpd, arcname), realname)


__all__ = ['mp', 'CPU_CNT', 'BOOLEAN_STATES', 'LOCALE_ENCODING', 'UUID4Generator',
           'detect_files', 'archive_files', 'recover_files']
