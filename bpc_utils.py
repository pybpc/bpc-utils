import binascii
import collections
import contextlib
import functools
import glob
import io
import itertools
import json
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
    import zlib  # pylint: disable=unused-import # noqa: F401
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
    if os.name == 'posix' and 'SC_NPROCESSORS_CONF' in os.sysconf_names:  # pylint: disable=no-member # pragma: no cover
        CPU_CNT = os.sysconf('SC_NPROCESSORS_CONF')  # pylint: disable=no-member
    elif 'sched_getaffinity' in os.__all__:  # pragma: no cover
        CPU_CNT = len(os.sched_getaffinity(0))  # pylint: disable=no-member
    else:  # pragma: no cover
        CPU_CNT = os.cpu_count() or 1
finally:    # alias and aftermath
    mp = multiprocessing
    del multiprocessing

parallel_available = mp is not None and CPU_CNT > 1

try:
    from contextlib import nullcontext  # novermin
except ImportError:  # backport contextlib.nullcontext for Python < 3.7 # pragma: no cover
    @contextlib.contextmanager
    def nullcontext(enter_result=None):
        yield enter_result

LOOKUP_TABLE = '_lookup_table.json'

PARSO_GRAMMAR_VERSIONS = []
for file in glob.iglob(os.path.join(parso.__path__[0], 'python', 'grammar*.txt')):
    version = os.path.basename(file)[7:-4]
    PARSO_GRAMMAR_VERSIONS.append((int(version[0]), int(version[1:])))
PARSO_GRAMMAR_VERSIONS = sorted(PARSO_GRAMMAR_VERSIONS)

del file, version  # pylint: disable=undefined-loop-variable


def get_parso_grammar_versions(minimum=None):
    """Get Python versions that parso supports to parse grammar.

    Args:
        minimum (str): filter result by this minimum version

    Returns:
        List[str]: a list of Python versions that parso supports to parse grammar

    Raises:
        ValueError: if ``minimum`` is invalid

    """
    if minimum is None:
        return ['{}.{}'.format(*v) for v in PARSO_GRAMMAR_VERSIONS]
    try:
        minimum = tuple(map(int, minimum.split('.')))
    except Exception:
        raise ValueError('invalid minimum version') from None
    else:
        return ['{}.{}'.format(*v) for v in PARSO_GRAMMAR_VERSIONS if v >= minimum]


def first_truthy(*args):
    """Return the first *truthy* value from a list of values.

    Args:
        *args: variable length argument list

            * If one positional argument is provided, it should be an iterable of the values.
            * If two or more positional arguments are provided, then the value list is the positional argument list.

    Returns:
        Any: the first *truthy* value, if no *truthy* values found or sequence is empty, return ``None``

    Raises:
        TypeError: if no arguments provided

    """
    if not args:
        raise TypeError('no arguments provided')
    if len(args) == 1:
        args = args[0]
    return next(filter(bool, args), None)  # pylint: disable=filter-builtin-not-iterating


def first_non_none(*args):
    """Return the first non-``None`` value from a list of values.

    Args:
        *args: variable length argument list

            * If one positional argument is provided, it should be an iterable of the values.
            * If two or more positional arguments are provided, then the value list is the positional argument list.

    Returns:
        Any: the first non-``None`` value, if all values are ``None`` or sequence is empty, return ``None``

    Raises:
        TypeError: if no arguments provided

    """
    if not args:
        raise TypeError('no arguments provided')
    if len(args) == 1:
        args = args[0]
    return next(filter(lambda x: x is not None, args), None)  # pylint: disable=filter-builtin-not-iterating


#: Dict[str, bool]: A mapping from string representation to boolean states.
#: The values are used for :func:`parse_boolean_state`.
_boolean_state_lookup = {
    '1': True,
    'yes': True,
    'y': True,
    'true': True,
    'on': True,
    '0': False,
    'no': False,
    'n': False,
    'false': False,
    'off': False,
}


def parse_boolean_state(s):
    """Parse a boolean state from a string representation.

    * These values are regarded as ``True``: ``'1'``, ``'yes'``, ``'y'``, ``'true'``, ``'on'``
    * These values are regarded as ``False``: ``'0'``, ``'no'``, ``'n'``, ``'false'``, ``'off'``

    Value matching is case **insensitive**.

    Args:
        s (Optional[str]): string representation of a boolean state

    Returns:
        Optional[bool]: the parsed boolean result, return ``None`` if input is ``None``

    Raises:
        ValueError: if ``s`` is an invalid boolean state value

    See Also:
        See :data:`_boolean_state_lookup` for default lookup mapping values.

    """
    if s is None:
        return None
    try:
        return _boolean_state_lookup[s.lower()]
    except KeyError:
        raise ValueError('invalid boolean state value {!r}'.format(s)) from None


#: Dict[str, str]: A mapping from string representation to linesep.
#: The values are used for :func:`parse_linesep`.
_linesep_lookup = {
    '\n': '\n',
    'lf': '\n',
    '\r\n': '\r\n',
    'crlf': '\r\n',
    '\r': '\r',
    'cr': '\r',
}


def parse_linesep(s):
    r"""Parse linesep from a string representation.

    * These values are regarded as ``'\n'``: ``'\n'``, ``'lf'``
    * These values are regarded as ``'\r\n'``: ``'\r\n'``, ``'crlf'``
    * These values are regarded as ``'\r'``: ``'\r'``, ``'cr'``

    Value matching is **case insensitive**.

    Args:
        s (Optional[str]): string representation of linesep

    Returns:
        Optional[Literal['\\n', '\\r\\n', '\\r']]: the parsed linesep result,
        return ``None`` if input is ``None`` or empty string

    Raises:
        ValueError: if ``s`` is an invalid linesep value

    See Also:
        See :data:`_linesep_lookup` for default lookup mapping values.

    """
    if not s:
        return None
    try:
        return _linesep_lookup[s.lower()]
    except KeyError:
        raise ValueError('invalid linesep value {!r}'.format(s)) from None


def parse_indentation(s):
    """Parse indentation from a string representation.

    * If a string of positive integer ``n`` is specified, then indentation is ``n`` spaces.
    * If ``'t'`` or ``'tab'`` is specified, then indentation is tab.

    Value matching is **case insensitive**.

    Args:
        s (Optional[str]): string representation of indentation

    Returns:
        Optional[str]: the parsed indentation result, return ``None`` if input is ``None`` or empty string

    Raises:
        ValueError: if ``s`` is an invalid indentation value

    """
    if not s:
        return None
    if s.lower() in {'t', 'tab'}:
        return '\t'
    try:
        n = int(s)
        if n <= 0:
            raise ValueError
        return ' ' * n
    except ValueError:
        raise ValueError('invalid indentation value {!r}'.format(s)) from None


class BPCSyntaxError(SyntaxError):
    """Syntax error detected when parsing code."""


class UUID4Generator:
    """UUID 4 generator wrapper to prevent UUID collisions."""

    def __init__(self, dash=True):
        """Constructor of UUID 4 generator wrapper.

        Args:
            dash (bool): whether the generated UUID string has dashes or not

        """
        self.used_uuids = set()
        self.dash = dash

    def gen(self):
        """Generate a new UUID 4 string that is guaranteed not to collide with used UUIDs.

        Returns:
            str: a new UUID 4 string

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
        filename (str): the name of the file

    Returns:
        bool: whether the file is a Python source file

    """
    if is_windows:  # pragma: no cover
        filename = filename.lower()
    return os.path.splitext(filename)[1] in {'.py', '.pyw'}


#: Wrapper function to perform glob expansion.
expand_glob_iter = glob.iglob if sys.version_info[:2] < (3, 5) else functools.partial(glob.iglob, recursive=True)


def detect_files(files):
    """Get a list of Python files to be processed according to user input.

    This will perform *glob* expansion on Windows, make all paths absolute,
    resolve symbolic links and remove duplicates.

    Args:
        files (List[str]): a list of files and directories to process
            (usually provided by users on command-line)

    Returns:
        List[str]: a list of Python files to be processed

    See Also:
        See :func:`expand_glob_iter` for more information.

    """
    file_list = []
    directory_queue = collections.deque()
    directory_visited = set()

    # perform glob expansion on windows
    if is_windows:  # pragma: no cover
        files = itertools.chain.from_iterable(map(expand_glob_iter, files))

    # find top-level files and directories
    for file in files:  # pylint: disable=redefined-outer-name
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
    """Archive the list of files into a *tar* file.

    Args:
        files (List[str]): a list of files to be archived (should be *absolute path*)
        archive_dir (os.PathLike): the directory to save the archive

    Returns:
        str: path to the generated *tar* archive

    """
    uuid_gen = UUID4Generator()
    lookup_table = {uuid_gen.gen() + '.py': file for file in files}
    archive_file = 'archive-{}-{}.tar'.format(time.strftime('%Y%m%d%H%M%S'), binascii.hexlify(os.urandom(8)))
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


def recover_files(archive_file):
    """Recover files from a *tar* archive.

    Args:
        archive_file (os.PathLike): path to the *tar* archive file

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
    """Detect encoding of Python source code as specified in `PEP 263`_.

    Args:
        code (bytes): the code to detect encoding

    Returns:
        str: the detected encoding, or the default encoding (``utf-8``)

    Raises:
        TypeError: if ``code`` is not a ``bytes`` string

    .. _PEP 263:
        https://www.python.org/dev/peps/pep-0263/

    """
    if not isinstance(code, bytes):
        raise TypeError("'code' should be bytes")
    with io.BytesIO(code) as file:  # pylint: disable=redefined-outer-name
        return tokenize.detect_encoding(file.readline)[0]


class MakeTextIO:
    """Context wrapper class to handle ``str`` and *file* objects together.

    Attributes:
        obj (Union[str, TextIO]): the object to manage in the context
        sio (Optional[StringIO]): the I/O object to manage in the context
            only if :attr:`self.obj <MakeTextIO.obj>` is ``str``
        pos (Optional[int]): the original offset of :attr:`self.obj <MakeTextIO.obj>`,
            only if :attr:`self.obj <MakeTextIO.obj>` is a *file* object

    """

    def __init__(self, obj):
        """Initialize context.

        Args:
            obj (Union[str, TextIO]): the object to manage in the context

        """
        self.obj = obj

    def __enter__(self):
        """Enter context.

        * If :attr:`self.obj <MakeTextIO.obj>` is ``str``, a
          ``StringIO`` will be created and returned.

        * If :attr:`self.obj <MakeTextIO.obj>` is a seekable *file* object,
          it will be seeked to the beginning and returned.

        * If :attr:`self.obj <MakeTextIO.obj>` is an unseekable *file* object,
          it will be returned directly.

        """
        if isinstance(self.obj, str):
            #: StringIO: the I/O object to manage in the context
            #:     only if :attr:`self.obj <MakeTextIO.obj>` is ``str``
            self.sio = io.StringIO(self.obj, newline='')  # turn off newline translation # pylint: disable=W0201
            return self.sio
        if self.obj.seekable():
            #: int: the original offset of :attr:`self.obj <MakeTextIO.obj>`,
            #:     only if :attr:`self.obj <MakeTextIO.obj>` is a seekable ``TextIO``
            self.pos = self.obj.tell()  # pylint: disable=W0201
            #: Union[str, TextIO]: the object to manage in the context
            self.obj.seek(0)
        return self.obj

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit context.

        * If :attr:`self.obj <MakeTextIO.obj>` is ``str``, the
          ``StringIO`` (:attr:`self.sio <MakeTextIO.sio>`) will be closed.

        * If :attr:`self.obj <MakeTextIO.obj>` is a seekable *file* object,
          its stream position (:attr:`self.pos <MakeTextIO.pos>`) will be recovered.

        """
        if isinstance(self.obj, str):
            self.sio.close()
        elif self.obj.seekable():
            self.obj.seek(self.pos)


def detect_linesep(code):
    r"""Detect linesep of Python source code.

    Args:
        code (Union[str, bytes, TextIO, parso.tree.NodeOrLeaf]): the code to detect linesep

    Returns:
        Literal['\\n', '\\r\\n', '\\r']: the detected linesep (one of ``'\n'``, ``'\r\n'`` and ``'\r'``)

    Notes:
        In case of mixed linesep, try voting by the number of occurrences of each linesep value.

        When there is a tie, prefer ``LF`` to ``CRLF``, prefer ``CRLF`` to ``CR``.

    """
    if isinstance(code, parso.tree.NodeOrLeaf):
        code = code.get_code()
    if isinstance(code, bytes):
        code = code.decode(detect_encoding(code))

    pool = {
        'CR': 0,
        'CRLF': 0,
        'LF': 0,
    }

    with MakeTextIO(code) as file:  # pylint: disable=redefined-outer-name
        for line in file:
            if line.endswith('\r'):
                pool['CR'] += 1
            elif line.endswith('\r\n'):
                pool['CRLF'] += 1
            elif line.endswith('\n'):
                pool['LF'] += 1

    # when there is a tie, prefer LF to CRLF, prefer CRLF to CR
    return max((pool['LF'], 3, '\n'), (pool['CRLF'], 2, '\r\n'), (pool['CR'], 1, '\r'))[2]


def detect_indentation(code):
    """Detect indentation of Python source code.

    Args:
        code (Union[str, bytes, TextIO, parso.tree.NodeOrLeaf]): the code to detect indentation

    Returns:
        str: the detected indentation sequence

    Notes:
        In case of mixed indentation, try voting by the number of occurrences of
        each indentation value (*spaces* and *tabs*).

        When there is a tie between *spaces* and *tabs*, prefer **4 spaces** for `PEP 8`_.

    .. _PEP 8:
        https://www.python.org/dev/peps/pep-0008/

    """
    if isinstance(code, parso.tree.NodeOrLeaf):
        code = code.get_code()
    if isinstance(code, bytes):
        code = code.decode(detect_encoding(code))

    pool = {
        'space': 0,
        'tab': 0
    }
    min_spaces = None

    with MakeTextIO(code) as file:  # pylint: disable=redefined-outer-name
        for token_info in tokenize.generate_tokens(file.readline):
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


def parso_parse(code, filename=None, *, version=None):  # pylint: disable=redefined-outer-name
    """Parse Python source code with parso.

    Args:
        code (Union[str, bytes]): the code to be parsed
        filename (str): an optional source file name to provide a context in case of error
        version (str): parse the code as this version (uses the latest version by default)

    Returns:
        parso.python.tree.Module: parso AST

    Raises:
        :exc:`BPCSyntaxError`: when source code contains syntax errors

    """
    grammar = parso.load_grammar(version=version if version is not None else get_parso_grammar_versions()[-1])
    if isinstance(code, bytes):
        code = code.decode(detect_encoding(code))
    module = grammar.parse(code, error_recovery=True)
    errors = grammar.iter_errors(module)
    if errors:
        error_messages = '\n'.join('[L%dC%d] %s' % (error.start_pos + (error.message,)) for error in errors)
        raise BPCSyntaxError('source file %r contains the following syntax errors:\n' %
                             first_non_none(filename, '<unknown>') + error_messages)
    return module


def _mp_map_wrapper(args):
    """Map wrapper function for :mod:`multiprocessing`.

    Args:
        args (Tuple[Callable, Iterable[Any], Mapping[str, Any]]): the function to execute,
            the positional arguments and the keyword arguments packed into a tuple

    Returns:
        Any: the function execution result

    """
    func, posargs, kwargs = args
    return func(*posargs, **kwargs)


def map_tasks(func, iterable, posargs=None, kwargs=None, *, processes=None, chunksize=None):
    """Execute tasks in parallel if ``multiprocessing`` is available, otherwise execute them sequentially.

    Args:
        func (Callable): the task function to execute
        iterable (Iterable[Any]): the items to process
        posargs (Optional[Iterable[Any]]): additional positional arguments to pass to ``func``
        kwargs (Optional[Mapping[str, Any]]): keyword arguments to pass to ``func``
        processes (Optional[int]): the number of worker processes (default: auto determine)
        chunksize (Optional[int]): chunk size for multiprocessing

    Returns:
        List[Any]: the return values of the task function applied on the input items and additional arguments

    """
    if posargs is None:
        posargs = ()
    if kwargs is None:
        kwargs = {}

    if not parallel_available or processes == 1:  # sequential execution
        return [func(item, *posargs, **kwargs) for item in iterable]

    with mp.Pool(processes=processes or CPU_CNT) as pool:  # parallel execution
        return pool.map(_mp_map_wrapper, [(func, (item,) + posargs, kwargs) for item in iterable], chunksize)


#: A lock for possibly concurrent tasks.
TaskLock = mp.Lock if parallel_available else nullcontext


class Config:
    """Configuration namespace.

    This class is inspired from :class:`argparse.Namespace` for storing
    internal attributes and/or configuration variables.

    """

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __contains__(self, key):
        return key in self.__dict__

    def __repr__(self):  # pragma: no cover
        type_name = type(self).__name__
        arg_strings = []
        star_args = {}
        for name, value in self.__dict__.items():
            if name.isidentifier():  # special case
                arg_strings.append('%s=%r' % (name, value))
            else:
                star_args[name] = value
        if star_args:
            arg_strings.append('**%s' % repr(star_args))
        return '%s(%s)' % (type_name, ', '.join(arg_strings))


__all__ = ['get_parso_grammar_versions', 'first_truthy', 'first_non_none',
           'parse_boolean_state', 'parse_linesep', 'parse_indentation', 'BPCSyntaxError', 'UUID4Generator',
           'detect_files', 'archive_files', 'recover_files', 'detect_encoding', 'detect_linesep',
           'detect_indentation', 'parso_parse', 'map_tasks', 'TaskLock', 'Config']
