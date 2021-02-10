"""Functions for parsing Python source code."""

import glob
import io
import os
import re
import token
import tokenize

import parso

from .misc import MakeTextIO, first_non_none
from .typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .typing import Dict, Linesep, List, Literal, Optional, TextIO, Tuple, Union

PARSO_GRAMMAR_VERSIONS = []  # type: List[Tuple[int, int]]
for grammar_file in glob.iglob(os.path.join(parso.__path__[0], 'python', 'grammar*.txt')):  # type: ignore[attr-defined]
    grammar_version = os.path.basename(grammar_file)[7:-4]
    PARSO_GRAMMAR_VERSIONS.append((int(grammar_version[0]), int(grammar_version[1:])))
PARSO_GRAMMAR_VERSIONS = sorted(PARSO_GRAMMAR_VERSIONS)


def get_parso_grammar_versions(minimum: 'Optional[str]' = None) -> 'List[str]':
    """Get Python versions that parso supports to parse grammar.

    Args:
        minimum: filter result by this minimum version

    Returns:
        a list of Python versions that parso supports to parse grammar

    Raises:
        TypeError: if ``minimum`` is not :obj:`str`
        ValueError: if ``minimum`` is invalid

    """
    if minimum is None:
        minimum_tuple = ()  # type: Tuple[int, ...]
    else:
        if not isinstance(minimum, str):
            raise TypeError('minimum version should be a string')
        if not re.fullmatch(r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)', minimum):
            raise ValueError('invalid minimum version')
        minimum_tuple = tuple(map(int, minimum.split('.')))
    return ['{}.{}'.format(*v) for v in PARSO_GRAMMAR_VERSIONS if v >= minimum_tuple]


class BPCSyntaxError(SyntaxError):
    """Syntax error detected when parsing code."""


def detect_encoding(code: bytes) -> str:
    """Detect encoding of Python source code as specified in :pep:`263`.

    Args:
        code: the code to detect encoding

    Returns:
        the detected encoding, or the default encoding (``utf-8``)

    Raises:
        TypeError: if ``code`` is not a :obj:`bytes` string
        SyntaxError: if both a BOM and a cookie are present, but disagree

    """
    if not isinstance(code, bytes):
        raise TypeError("'code' should be bytes")
    with io.BytesIO(code) as file:
        return tokenize.detect_encoding(file.readline)[0]


def detect_linesep(code: 'Union[str, bytes, TextIO, parso.tree.NodeOrLeaf]') -> 'Linesep':
    r"""Detect linesep of Python source code.

    Args:
        code: the code to detect linesep

    Returns:
        :data:`~bpc_utils.Linesep`: the detected linesep (one of ``'\n'``, ``'\r\n'`` and ``'\r'``)

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
    }  # type: Dict[Literal['CR', 'CRLF', 'LF'], int]

    with MakeTextIO(cast('Union[str, TextIO]', code)) as file:
        for line in file:
            if line.endswith('\r'):
                pool['CR'] += 1
            elif line.endswith('\r\n'):
                pool['CRLF'] += 1
            elif line.endswith('\n'):
                pool['LF'] += 1

    # when there is a tie, prefer LF to CRLF, prefer CRLF to CR
    return cast('Linesep', max((pool['LF'], 3, '\n'), (pool['CRLF'], 2, '\r\n'), (pool['CR'], 1, '\r'))[2])


def detect_indentation(code: 'Union[str, bytes, TextIO, parso.tree.NodeOrLeaf]') -> str:
    """Detect indentation of Python source code.

    Args:
        code: the code to detect indentation

    Returns:
        the detected indentation sequence

    Raises:
        :exc:`~tokenize.TokenError`: when failed to tokenize the source code under certain cases,
            see documentation of :exc:`~tokenize.TokenError` for more details

    Notes:
        In case of mixed indentation, try voting by the number of occurrences of
        each indentation value (*spaces* and *tabs*).

        When there is a tie between *spaces* and *tabs*, prefer **4 spaces** for :pep:`8`.

    """
    if isinstance(code, parso.tree.NodeOrLeaf):
        code = code.get_code()
    if isinstance(code, bytes):
        code = code.decode(detect_encoding(code))

    pool = {
        'space': 0,
        'tab': 0
    }  # type: Dict[Literal['space', 'tab'], int]
    min_spaces = None  # type: Optional[int]

    with MakeTextIO(cast('Union[str, TextIO]', code)) as file:
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
        return ' ' * cast(int, min_spaces)
    if pool['space'] < pool['tab']:
        return '\t'
    return ' ' * 4  # same number of spaces and tabs, prefer 4 spaces for PEP 8


def parso_parse(code: 'Union[str, bytes]', filename: 'Optional[str]' = None, *,
                version: 'Optional[str]' = None) -> 'parso.python.tree.Module':
    """Parse Python source code with parso.

    Args:
        code: the code to be parsed
        filename: an optional source file name to provide a context in case of error
        version: parse the code as this version (uses the latest version by default)

    Returns:
        parso AST

    Raises:
        :exc:`BPCSyntaxError`: when source code contains syntax errors

    """
    filename = first_non_none(filename, '<unknown>')
    grammar = parso.load_grammar(version=version if version is not None else get_parso_grammar_versions()[-1])
    if isinstance(code, bytes):
        try:
            code = code.decode(detect_encoding(code))
        except SyntaxError as e:
            raise BPCSyntaxError('failed to detect encoding for source file %r: %s' % (filename, e)) from None
    module = grammar.parse(code, error_recovery=True)  # type: parso.python.tree.Module
    errors = grammar.iter_errors(module)
    if errors:
        error_messages = '\n'.join('[L%dC%d] %s' % (error.start_pos + (error.message,)) for error in errors)
        raise BPCSyntaxError('source file %r contains the following syntax errors:\n%s' % (filename, error_messages))
    return module


__all__ = ['get_parso_grammar_versions', 'BPCSyntaxError', 'detect_encoding', 'detect_linesep', 'detect_indentation',
           'parso_parse']
