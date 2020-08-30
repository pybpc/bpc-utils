"""Functions for parsing Python source code."""

import glob
import io
import os
import token
import tokenize

import parso

from .misc import MakeTextIO, first_non_none

PARSO_GRAMMAR_VERSIONS = []
for grammar_file in glob.iglob(os.path.join(parso.__path__[0], 'python', 'grammar*.txt')):
    grammar_version = os.path.basename(grammar_file)[7:-4]
    PARSO_GRAMMAR_VERSIONS.append((int(grammar_version[0]), int(grammar_version[1:])))
PARSO_GRAMMAR_VERSIONS = sorted(PARSO_GRAMMAR_VERSIONS)


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


class BPCSyntaxError(SyntaxError):
    """Syntax error detected when parsing code."""


def detect_encoding(code):
    """Detect encoding of Python source code as specified in :pep:`263`.

    Args:
        code (bytes): the code to detect encoding

    Returns:
        str: the detected encoding, or the default encoding (``utf-8``)

    Raises:
        TypeError: if ``code`` is not a :obj:`bytes` string

    """
    if not isinstance(code, bytes):
        raise TypeError("'code' should be bytes")
    with io.BytesIO(code) as file:
        return tokenize.detect_encoding(file.readline)[0]


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

    with MakeTextIO(code) as file:
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

        When there is a tie between *spaces* and *tabs*, prefer **4 spaces** for :pep:`8`.

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

    with MakeTextIO(code) as file:
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


def parso_parse(code, filename=None, *, version=None):
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


__all__ = ['get_parso_grammar_versions', 'BPCSyntaxError', 'detect_encoding', 'detect_linesep', 'detect_indentation',
           'parso_parse']
