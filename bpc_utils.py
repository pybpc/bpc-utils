import binascii
import collections
import glob
import io
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
import token
import tokenize
import uuid

import parso

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

LOCALE_ENCODING = locale.getpreferredencoding(False)

LOOKUP_TABLE = '_lookup_table.json'

PARSO_GRAMMAR_VERSIONS = []
for file in glob.iglob(os.path.join(parso.__path__[0], 'python', 'grammar*.txt')):
    version = os.path.basename(file)[7:-4]
    PARSO_GRAMMAR_VERSIONS.append((int(version[0]), int(version[1:])))
PARSO_GRAMMAR_VERSIONS = sorted(PARSO_GRAMMAR_VERSIONS)

del file, version


def get_parso_grammar_versions(minimum='0.0'):
    """Get Python versions that parso supports to parse grammar.

    Args:
        - `minimum` -- `str`, filter result by this minimum version

    Returns:
        - `List[str]` -- a list of Python versions that parso supports to parse grammar

    """
    minimum = tuple(map(int, minimum.split('.')))
    return ['{}.{}'.format(*v) for v in PARSO_GRAMMAR_VERSIONS if v >= minimum]


def first_truthy(*args):
    """Return the first truthy value from a list of values.

    Args:
        - if one positional argument is provided, it should be an iterable of the values
        - if two or more positional arguments are provided, then the value list is the positional argument list

    Returns:
        - `Any` -- the first truthy value

    """
    if not args:
        raise TypeError('no arguments provided')
    if len(args) == 1:
        args = args[0]
    try:
        return next(filter(bool, args))
    except StopIteration:
        raise ValueError('no truthy values found, or sequence is empty') from None


def first_non_none(*args):
    """Return the first non-None value from a list of values.

    Args:
        - if one positional argument is provided, it should be an iterable of the values
        - if two or more positional arguments are provided, then the value list is the positional argument list

    Returns:
        - `Any` -- the first non-None value

    """
    if not args:
        raise TypeError('no arguments provided')
    if len(args) == 1:
        args = args[0]
    try:
        return next(filter(lambda x: x is not None, args))
    except StopIteration:
        raise ValueError('all values are None, or sequence is empty') from None


def parse_boolean_state(s):
    """Parse a boolean state from a string representation.
    These values are regarded as `True`: '1', 'yes', 'y', 'true', 'on'
    These values are regarded as `False`: '0', 'no', 'n', 'false', 'off'
    Value matching is case insensitive.

    Args:
        - `s` -- `str`, string representation of a boolean state

    Returns:
        - `bool` -- the parsed boolean result

    """
    s = s.lower()
    if s in ('1', 'yes', 'y', 'true', 'on'):
        return True
    if s in ('0', 'no', 'n', 'false', 'off'):
        return False
    raise ValueError('invalid boolean state value {!r}'.format(s))


def parse_linesep(s):
    """Parse linesep from a string representation.
    These values are regarded as '\n': '\n', 'lf'
    These values are regarded as '\r\n': '\r\n', 'crlf'
    These values are regarded as '\r': '\r', 'cr'
    Value matching is case insensitive.

    Args:
        - `s` -- `str`, string representation of linesep

    Returns:
        - `str` -- the parsed linesep result

    """
    s = s.lower()
    if s in ('\n', 'lf'):
        return '\n'
    if s in ('\r\n', 'crlf'):
        return '\r\n'
    if s in ('\r', 'cr'):
        return '\r'
    raise ValueError('invalid linesep value {!r}'.format(s))


def parse_indentation(s):
    """Parse indentation from a string representation.
    If a string of positive integer `n` is specified, then indentation is `n` spaces.
    If 't' or 'tab' is specified, then indentation is tab.
    Value matching is case insensitive.

    Args:
        - `s` -- `str`, string representation of tabsize

    Returns:
        - `str` -- the parsed indentation result

    """
    s = s.lower()
    if s in ('t', 'tab'):
        return '\t'
    try:
        n = int(s)
        if n <= 0:
            raise ValueError
        return ' ' * n
    except ValueError:
        raise ValueError('invalid tabsize value {!r}'.format(s)) from None


class ConvertError(SyntaxError):
    """Convertion error due to syntax error."""


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
    archive_file = 'archive-{}-{}.tar'.format(time.strftime('%Y%m%d%H%M%S'), binascii.hexlify(os.urandom(8)))
    archive_mode = 'w'
    if has_gz_support:  # pragma: no cover
        archive_file += '.gz'
        archive_mode += ':gz'
    os.makedirs(archive_dir, exist_ok=True)
    with tarfile.open(os.path.join(archive_dir, archive_file), archive_mode) as tarf:
        for arcname, realname in lookup_table.items():
            tarf.add(realname, arcname)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', prefix='bpc-archive-lookup-', suffix='.json', delete=False) as tmpf:
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
        with tempfile.TemporaryDirectory(prefix='bpc-archive-extract-') as tmpd:
            tarf.extractall(tmpd)
            with open(os.path.join(tmpd, LOOKUP_TABLE)) as lookupf:
                lookup_table = json.load(lookupf)
            for arcname, realname in lookup_table.items():
                os.makedirs(os.path.dirname(realname), exist_ok=True)
                shutil.move(os.path.join(tmpd, arcname), realname)


def detect_encoding(code):
    """Detect encoding of Python source code as specified in PEP 263.

    Args:
     - `code` -- `bytes`, the code to detect encoding

    Returns:
     - `str` -- the detected encoding, or the default encoding ('utf-8')

    """
    with io.BytesIO(code) as file:
        return tokenize.detect_encoding(file.readline)[0]


def detect_linesep(code):
    """Detect linesep of Python source code.

    Args:
     - `code` -- `Union[str, bytes, parso.tree.NodeOrLeaf]`, the code to detect linesep

    Returns:
     - `str` -- the detected linesep (one of '\n', '\r\n' and '\r')

    """
    if isinstance(code, parso.tree.NodeOrLeaf):
        code = code.get_code()
    is_bytes = isinstance(code, bytes)

    pool = {
        'CR': 0,
        'CRLF': 0,
        'LF': 0,
    }
    CR = b'\r' if is_bytes else '\r'
    CRLF = b'\r\n' if is_bytes else '\r\n'
    LF = b'\n' if is_bytes else '\n'

    for line in code.splitlines(keepends=True):
        if line.endswith(CR):
            pool['CR'] += 1
        elif line.endswith(CRLF):
            pool['CRLF'] += 1
        elif line.endswith(LF):
            pool['LF'] += 1

    return max((pool['LF'], 3, '\n'), (pool['CRLF'], 2, '\r\n'), (pool['CR'], 1, '\r'))[2]


def detect_indentation(code):
    """Detect indentation of Python source code.

    Args:
        - `code` -- `Union[str, bytes, parso.tree.NodeOrLeaf]`, the code to detect indentation

    Returns:
        - `str` -- the detected indentation sequence

    """
    if isinstance(code, parso.tree.NodeOrLeaf):
        code = code.get_code()
    if isinstance(code, str):
        code = code.encode()

    pool = {
        'space': 0,
        'tab': 0
    }
    min_spaces = None

    with io.BytesIO(code) as file:
        for token_info in tokenize.tokenize(file.readline):
            if token_info.type == token.INDENT:
                if '\t' in token_info.string and ' ' in token_info.string:
                    continue  # skip indentation with mixed spaces and tabs
                if '\t' in token_info.string:
                    pool['tab'] += 1
                else:
                    pool['space'] += 1
                    if min_spaces is None:
                        min_spaces = len(token_info.string)
                    else:
                        min_spaces = min(min_spaces, len(token_info.string))

    if pool['space'] > pool['tab']:
        return ' ' * min_spaces
    if pool['space'] < pool['tab']:
        return '\t'
    return ' ' * 4  # same number of spaces and tabs, prefer 4 spaces for PEP 8


def parso_parse(code, file=None, version=None, encoding=None, errors='strict'):
    """Parse Python source code with parso.

    Args:
     - `code` -- `Union[str, bytes]`, the code to be parsed
     - `file` -- `str`, an optional source file name to provide a context in case of error
     - `version` -- `str`, parse the code as this version (uses the latest version by default)
     - `encoding` -- `str`, the encoding to decode `code` if it is `bytes`, if not specified
        the encoding will be detected as specified in PEP 263
     - `errors` -- `str`, decoding error handling scheme

    Returns:
     - `parso.python.tree.Module` -- parso AST

    Raises:
     - `ConvertError` -- when source code contains syntax errors

    """
    grammar = parso.load_grammar(version=version or get_parso_grammar_versions()[-1])
    if isinstance(code, bytes):
        code = code.decode(encoding or detect_encoding(code), errors)
    module = grammar.parse(code, error_recovery=True)
    errors = grammar.iter_errors(module)
    if errors:
        error_messages = '\n'.join('[L%dC%d] %s' % (error.start_pos[0], error.start_pos[1], error.message) for error in errors)
        raise ConvertError('source file %r contains the following syntax errors:\n' % (file or '<unknown>') + error_messages)
    return module


__all__ = ['mp', 'CPU_CNT', 'LOCALE_ENCODING', 'get_parso_grammar_versions', 'first_truthy', 'first_non_none',
           'parse_boolean_state', 'parse_linesep', 'parse_indentation', 'ConvertError', 'UUID4Generator',
           'detect_files', 'archive_files', 'recover_files', 'detect_encoding', 'detect_linesep',
           'detect_indentation', 'parso_parse']
