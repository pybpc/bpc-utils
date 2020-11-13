"""Utility functions for argument parsing."""

from .typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .typing import Dict, Final, Linesep, Optional, Union


def parse_positive_integer(s: 'Optional[Union[str, int]]') -> 'Optional[int]':
    """Parse a positive integer from a string representation.

    Args:
        s: string representation of a positive integer, or just an integer

    Returns:
        the parsed integer result, return :data:`None` if input is :data:`None` or empty string

    Raises:
        TypeError: if ``s`` is not :obj:`str` or :obj:`int`
        ValueError: if ``s`` is an invalid positive integer value

    """
    if s is None or s == '':  # pylint: disable=compare-to-empty-string
        return None
    if not isinstance(s, (str, int)):
        raise TypeError('expect str or int, got {!r}'.format(s))
    try:
        value = int(s)
    except ValueError:
        raise ValueError('expect an integer value, got {!r}'.format(s)) from None
    if value <= 0:
        raise ValueError('expect integer value to be positive, got {!r}'.format(value))
    return value


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
}  # type: Final[Dict[str, bool]]


def parse_boolean_state(s: 'Optional[str]') -> 'Optional[bool]':
    """Parse a boolean state from a string representation.

    * These values are regarded as :data:`True`: ``'1'``, ``'yes'``, ``'y'``, ``'true'``, ``'on'``
    * These values are regarded as :data:`False`: ``'0'``, ``'no'``, ``'n'``, ``'false'``, ``'off'``

    Value matching is case **insensitive**.

    Args:
        s: string representation of a boolean state

    Returns:
        the parsed boolean result, return :data:`None` if input is :data:`None`

    Raises:
        ValueError: if ``s`` is an invalid boolean state value

    See Also:
        See :data:`~bpc_utils.argparse._boolean_state_lookup` for default lookup mapping values.

    """
    if s is None:
        return None
    try:
        return _boolean_state_lookup[s.lower()]
    except KeyError:
        raise ValueError('invalid boolean state value {!r}'.format(s)) from None


_linesep_lookup = {
    '\n': '\n',
    'lf': '\n',
    '\r\n': '\r\n',
    'crlf': '\r\n',
    '\r': '\r',
    'cr': '\r',
}  # type: Final[Dict[str, Linesep]]


def parse_linesep(s: 'Optional[str]') -> 'Optional[Linesep]':
    r"""Parse linesep from a string representation.

    * These values are regarded as ``'\n'``: ``'\n'``, ``'lf'``
    * These values are regarded as ``'\r\n'``: ``'\r\n'``, ``'crlf'``
    * These values are regarded as ``'\r'``: ``'\r'``, ``'cr'``

    Value matching is **case insensitive**.

    Args:
        s: string representation of linesep

    Returns:
        Optional[:data:`~bpc_utils.Linesep`]: the parsed linesep result,
        return :data:`None` if input is :data:`None` or empty string

    Raises:
        ValueError: if ``s`` is an invalid linesep value

    See Also:
        See :data:`~bpc_utils.argparse._linesep_lookup` for default lookup mapping values.

    """
    if not s:
        return None
    try:
        return _linesep_lookup[s.lower()]
    except KeyError:
        raise ValueError('invalid linesep value {!r}'.format(s)) from None


def parse_indentation(s: 'Optional[Union[str, int]]') -> 'Optional[str]':
    r"""Parse indentation from a string representation.

    * If an integer or a string of positive integer ``n`` is specified, then indentation is ``n`` spaces.
    * If ``'t'`` or ``'tab'`` is specified, then indentation is tab.
    * If ``'\t'``  (the tab character itself) or a string consisting only of the space character (U+0020)
      is specified, it is returned directly.

    Value matching is **case insensitive**.

    Args:
        s: string representation of indentation

    Returns:
        the parsed indentation result, return :data:`None` if input is :data:`None` or empty string

    Raises:
        TypeError: if ``s`` is not :obj:`str` or :obj:`int`
        ValueError: if ``s`` is an invalid indentation value

    """
    if s is None or s == '':  # pylint: disable=compare-to-empty-string
        return None
    if not isinstance(s, (str, int)):
        raise TypeError('expect str or int, got {!r}'.format(s))
    if isinstance(s, str):
        if s.lower() in {'t', 'tab', '\t'}:
            return '\t'
        if s == ' ' * len(s):
            return s
    try:
        n = int(s)
        if n <= 0:
            raise ValueError
        return ' ' * n
    except ValueError:
        raise ValueError('invalid indentation value {!r}'.format(s)) from None


__all__ = ['parse_positive_integer', 'parse_boolean_state', 'parse_linesep', 'parse_indentation']
