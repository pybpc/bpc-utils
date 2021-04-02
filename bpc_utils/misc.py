"""Miscellaneous utilities."""

import datetime
import functools
import io
import keyword
import operator
import platform
import textwrap
import uuid

from .typing import TYPE_CHECKING, MutableMapping, overload

if TYPE_CHECKING:
    from types import TracebackType  # isort: split
    from .typing import (Dict, Generator, Iterable, Iterator, List, Mapping, NoReturn, Optional,
                         Set, T, TextIO, Tuple, Type, Union)

# backport contextlib.nullcontext for Python < 3.7
try:
    from contextlib import nullcontext  # pylint: disable=unused-import  # novermin
except ImportError:  # pragma: no cover
    class nullcontext:  # type: ignore[no-redef]
        def __init__(self, enter_result: 'T' = None) -> None:  # type: ignore[assignment]
            self.enter_result = enter_result  # type: T

        def __enter__(self) -> 'T':
            return self.enter_result

        def __exit__(self, exc_type: 'Optional[Type[BaseException]]', exc_value: 'Optional[BaseException]',
                     traceback: 'Optional[TracebackType]') -> None:
            pass

is_windows = platform.system() == 'Windows'


def current_time_with_tzinfo() -> 'datetime.datetime':
    """Get the current time with local time zone information.

    Returns:
        datetime object representing current time with local time zone information

    """
    return datetime.datetime.now(datetime.timezone.utc).astimezone()


@overload
def first_truthy(*args: 'T') -> 'Optional[T]':
    ...  # pragma: no cover


@overload
def first_truthy(args: 'Iterable[T]') -> 'Optional[T]':  # noqa: F811
    ...  # pragma: no cover


def first_truthy(*args):  # type: ignore[no-untyped-def]  # noqa: F811
    """Return the first *truthy* value from a list of values.

    Args:
        *args: variable length argument list

            * If one positional argument is provided, it should be an iterable of the values.
            * If two or more positional arguments are provided, then the value list is the positional argument list.

    Returns:
        the first *truthy* value, if no *truthy* values found or sequence is empty, return :data:`None`

    Raises:
        TypeError: if no arguments provided

    """
    if not args:
        raise TypeError('no arguments provided')
    if len(args) == 1:
        args = args[0]
    return next(filter(bool, args), None)  # pylint: disable=filter-builtin-not-iterating


@overload
def first_non_none(*args: 'T') -> 'Optional[T]':
    ...  # pragma: no cover


@overload
def first_non_none(args: 'Iterable[T]') -> 'Optional[T]':  # noqa: F811
    ...  # pragma: no cover


def first_non_none(*args):  # type: ignore[no-untyped-def]  # noqa: F811
    """Return the first non-:data:`None` value from a list of values.

    Args:
        *args: variable length argument list

            * If one positional argument is provided, it should be an iterable of the values.
            * If two or more positional arguments are provided, then the value list is the positional argument list.

    Returns:
        the first non-:data:`None` value, if all values are :data:`None` or sequence is empty, return :data:`None`

    Raises:
        TypeError: if no arguments provided

    """
    if not args:
        raise TypeError('no arguments provided')
    if len(args) == 1:
        args = args[0]
    return next(filter(lambda x: x is not None, args), None)  # pylint: disable=filter-builtin-not-iterating


class UUID4Generator:
    """UUID 4 generator wrapper to prevent UUID collisions."""

    def __init__(self, dash: bool = True) -> None:
        """Constructor of UUID 4 generator wrapper.

        Args:
            dash: whether the generated UUID string has dashes or not

        """
        self.used_uuids = set()  # type: Set[str]
        self.dash = dash

    def gen(self) -> str:
        """Generate a new UUID 4 string that is guaranteed not to collide with used UUIDs.

        Returns:
            a new UUID 4 string

        """
        while True:
            new_uuid = uuid.uuid4()
            nuid = str(new_uuid) if self.dash else new_uuid.hex
            if nuid not in self.used_uuids:  # pragma: no cover
                break
        self.used_uuids.add(nuid)
        return nuid


class MakeTextIO:
    """Context wrapper class to handle :obj:`str` and *file* objects together.

    Attributes:
        obj (Union[str, TextIO]): the object to manage in the context
        sio (Optional[StringIO]): the I/O object to manage in the context
            only if :attr:`self.obj <MakeTextIO.obj>` is :obj:`str`
        pos (Optional[int]): the original offset of :attr:`self.obj <MakeTextIO.obj>`,
            only if :attr:`self.obj <MakeTextIO.obj>` is a seekable *file* object

    """

    def __init__(self, obj: 'Union[str, TextIO]') -> None:
        """Initialize context.

        Args:
            obj: the object to manage in the context

        """
        self.obj = obj

    def __enter__(self) -> 'TextIO':
        """Enter context.

        * If :attr:`self.obj <MakeTextIO.obj>` is :obj:`str`, a
          :class:`~io.StringIO` will be created and returned.

        * If :attr:`self.obj <MakeTextIO.obj>` is a seekable *file* object,
          it will be seeked to the beginning and returned.

        * If :attr:`self.obj <MakeTextIO.obj>` is an unseekable *file* object,
          it will be returned directly.

        """
        if isinstance(self.obj, str):
            #: StringIO: the I/O object to manage in the context
            #: only if :attr:`self.obj <MakeTextIO.obj>` is :obj:`str`
            self.sio = io.StringIO(self.obj, newline='')  # turn off newline translation  # pylint: disable=W0201
            return self.sio
        if self.obj.seekable():
            #: int: the original offset of :attr:`self.obj <MakeTextIO.obj>`,
            #: only if :attr:`self.obj <MakeTextIO.obj>` is a seekable
            #: :class:`TextIO <io.TextIOWrapper>`
            self.pos = self.obj.tell()  # pylint: disable=W0201
            #: Union[str, TextIO]: the object to manage in the context
            self.obj.seek(0)
        return self.obj

    def __exit__(self, exc_type: 'Optional[Type[BaseException]]', exc_value: 'Optional[BaseException]',
                 traceback: 'Optional[TracebackType]') -> None:
        """Exit context.

        * If :attr:`self.obj <MakeTextIO.obj>` is :obj:`str`, the
          :class:`~io.StringIO` (:attr:`self.sio <MakeTextIO.sio>`) will be closed.

        * If :attr:`self.obj <MakeTextIO.obj>` is a seekable *file* object,
          its stream position (:attr:`self.pos <MakeTextIO.pos>`) will be recovered.

        """
        if isinstance(self.obj, str):
            self.sio.close()
        elif self.obj.seekable():
            self.obj.seek(self.pos)


class Config(MutableMapping[str, object]):
    """Configuration namespace.

    This class is inspired from :class:`argparse.Namespace` for storing
    internal attributes and/or configuration variables.

    >>> config = Config(foo='var', bar=True)
    >>> config.foo
    'var'
    >>> config['bar']
    True
    >>> config.bar = 'boo'
    >>> del config['foo']
    >>> config
    Config(bar='boo')

    """

    def __init__(self, **kwargs: object) -> None:
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __contains__(self, key: object) -> bool:
        return key in self.__dict__

    def __iter__(self) -> 'Iterator[str]':
        return iter(self.__dict__)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __getitem__(self, key: str) -> object:
        return self.__dict__[key]

    def __setitem__(self, key: str, value: object) -> None:
        self.__dict__[key] = value

    def __delitem__(self, key: str) -> None:
        del self.__dict__[key]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Config) and self.__dict__ == other.__dict__

    def __repr__(self) -> str:
        type_name = type(self).__name__
        arg_strings = []  # type: List[str]
        star_args = {}  # type: Dict[str, object]
        for name, value in sorted(self.__dict__.items()):
            if name.isidentifier() and not keyword.iskeyword(name) and name != '__debug__':
                arg_strings.append('%s=%r' % (name, value))
            else:  # wrap invalid names into a dict to make __repr__ round-trip
                star_args[name] = value
        if star_args:
            arg_strings.append('**%s' % repr(star_args))
        return '%s(%s)' % (type_name, ', '.join(arg_strings))


class Placeholder:
    """Placeholder for string interpolation.

    :class:`Placeholder` objects can be concatenated with :obj:`str`, other :class:`Placeholder` objects
    and :class:`StringInterpolation` objects via the '+' operator.

    :class:`Placeholder` objects should be regarded as immutable. Please do not modify the ``name``
    attribute. Build new objects instead.

    """

    def __init__(self, name: str) -> None:
        """Initialize Placeholder.

        Args:
            name: name of the placeholder

        Raises:
            TypeError: if ``name`` is not :obj:`str`

        """
        if not isinstance(name, str):
            raise TypeError('placeholder name must be str')
        self.name = name

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.name == other.name  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((self.name,))

    def __repr__(self) -> str:
        return '{}({!r})'.format(type(self).__name__, self.name)

    def __str__(self) -> 'NoReturn':
        raise TypeError('Placeholder objects cannot be converted to str, consider using '
                        'repr() if you want a string representation')

    def __add__(self, other: object) -> 'StringInterpolation':
        if isinstance(other, str):
            return StringInterpolation.from_components(('', other), (self,))
        if isinstance(other, Placeholder):
            return StringInterpolation.from_components(('', '', ''), (self, other))
        if isinstance(other, StringInterpolation):
            return StringInterpolation.from_components(('',) + other.literals, (self,) + other.placeholders)
        return NotImplemented

    def __radd__(self, other: object) -> 'StringInterpolation':
        if isinstance(other, str):
            return StringInterpolation.from_components((other, ''), (self,))
        return NotImplemented


class StringInterpolation:
    """A string with placeholders to be filled in.

    This looks like an object-oriented format string, but making sure that string literals are
    always interpreted literally (so no need to manually do escaping). The boundaries between string
    literals and placeholders are very clear. Filling in a placeholder will never inject a new
    placeholder, protecting string integrity for multiple-round interpolation.

    >>> s1 = '%(injected)s'
    >>> s2 = 'hello'
    >>> s = StringInterpolation('prefix ', Placeholder('q1'), ' infix ', Placeholder('q2'), ' suffix')
    >>> str(s % {'q1': s1} % {'q2': s2})
    'prefix %(injected)s infix hello suffix'

    (This can be regarded as an improved version of :meth:`string.Template.safe_substitute`.)

    Multiple-round interpolation is tricky to do with a traditional format string. In order to do things
    correctly and avoid format string injection vulnerabilities, you need to perform escapes very carefully.

    >>> fs = 'prefix %(q1)s infix %(q2)s suffix'
    >>> fs % {'q1': s1} % {'q2': s2}
    Traceback (most recent call last):
        ...
    KeyError: 'q2'
    >>> fs = 'prefix %(q1)s infix %%(q2)s suffix'
    >>> fs % {'q1': s1} % {'q2': s2}
    Traceback (most recent call last):
        ...
    KeyError: 'injected'
    >>> fs % {'q1': s1.replace('%', '%%')} % {'q2': s2}
    'prefix %(injected)s infix hello suffix'

    :class:`StringInterpolation` objects can be concatenated with :obj:`str`, :class:`Placeholder` objects
    and other :class:`StringInterpolation` objects via the '+' operator.

    :class:`StringInterpolation` objects should be regarded as immutable. Please do not modify the
    ``literals`` and ``placeholders`` attributes. Build new objects instead.

    """

    def __init__(self, *args: 'Union[str, Placeholder, StringInterpolation]') -> None:
        """Initialize StringInterpolation. ``args`` will be concatenated to construct a
        :class:`StringInterpolation` object.

        >>> StringInterpolation('prefix', Placeholder('data'), 'suffix')
        StringInterpolation('prefix', Placeholder('data'), 'suffix')

        Args:
            args: the components to construct a :class:`StringInterpolation` object

        """
        if not args:
            self.literals = ('',)  # type: Tuple[str, ...]
            self.placeholders = ()  # type: Tuple[Placeholder, ...]
            return
        obj = functools.reduce(operator.add, args, StringInterpolation())
        self.literals = obj.literals
        self.placeholders = obj.placeholders

    @staticmethod
    def from_components(literals: 'Iterable[str]', placeholders: 'Iterable[Placeholder]') -> 'StringInterpolation':
        """Construct a :class:`StringInterpolation` object from ``literals`` and ``placeholders`` components.
        This method is more efficient than the :func:`StringInterpolation` constructor, but it is mainly
        intended for internal use.

        >>> StringInterpolation.from_components(
        ...     ('prefix', 'infix', 'suffix'),
        ...     (Placeholder('data1'), Placeholder('data2'))
        ... )
        StringInterpolation('prefix', Placeholder('data1'), 'infix', Placeholder('data2'), 'suffix')

        Args:
            literals: the literal components in order
            placeholders: the :class:`Placeholder` components in order

        Returns:
            the constructed :class:`StringInterpolation` object

        Raises:
            TypeError: if ``literals`` is :obj:`str`; if ``literals`` contains non-:obj:`str` values;
                if ``placeholders`` contains non-:class:`Placeholder` values
            ValueError: if the length of ``literals`` is not exactly one more than the length of ``placeholders``

        """
        obj = StringInterpolation()

        if isinstance(literals, str):
            raise TypeError('literals must be a non-string iterable')

        obj.literals = tuple(literals)
        obj.placeholders = tuple(placeholders)

        if len(obj.literals) - len(obj.placeholders) != 1:
            raise ValueError('the number of literals must be exactly one more than the number of placeholders')
        for literal in obj.literals:
            if not isinstance(literal, str):
                raise TypeError('literals contain non-string value: {!r}'.format(literal))
        for placeholder in obj.placeholders:
            if not isinstance(placeholder, Placeholder):
                raise TypeError('placeholders contain non-Placeholder value: {!r}'.format(placeholder))

        return obj

    def iter_components(self) -> 'Generator[Union[str, Placeholder], None, None]':
        """Generator to iterate all components of this :class:`StringInterpolation` object in order.

        >>> list(StringInterpolation('prefix', Placeholder('data'), 'suffix').iter_components())
        ['prefix', Placeholder('data'), 'suffix']

        Returns:
            generator containing the components of this :class:`StringInterpolation` object in order

        """
        for literal, placeholder in zip(self.literals, self.placeholders):
            yield literal
            yield placeholder
        yield self.literals[-1]

    def __repr__(self) -> str:
        return '{}({})'.format(type(self).__name__, ', '.join(repr(c) for c in self.iter_components() if c))

    def __str__(self) -> str:
        """Returns the fully-substituted string interpolation result.

        >>> str(StringInterpolation('prefix hello suffix'))
        'prefix hello suffix'

        Returns:
            the fully-substituted string interpolation result

        Raises:
            ValueError: if there are still unsubstituted placeholders in this :class:`StringInterpolation` object

        """
        if self.placeholders:
            raise ValueError(
                'cannot convert this StringInterpolation object to str (retrieve interpolation result) '
                'because it contains the following unsubstituted placeholders: '
                + ', '.join(map(repr, sorted(set(placeholder.name for placeholder in self.placeholders))))
                + '; consider using repr() if you want a string representation of this object'
            )
        return self.literals[0]

    def __eq__(self, other: object) -> bool:
        if (type(self) is type(other) and self.literals == other.literals   # type: ignore[attr-defined]
                and self.placeholders == other.placeholders):  # type: ignore[attr-defined]
            return True
        if isinstance(other, str) and self.literals == (other,):
            return True
        if isinstance(other, Placeholder) and self.placeholders == (other,) and self.literals == ('', ''):
            return True
        return False

    def __hash__(self) -> int:
        if len(self.literals) == 1:
            return hash(self.literals[0])
        if self.literals == ('', ''):
            return hash(self.placeholders[0])
        return hash((self.literals, self.placeholders))

    def __bool__(self) -> bool:
        return len(self.literals) > 1 or bool(self.literals[0])

    def __add__(self, other: object) -> 'StringInterpolation':
        if isinstance(other, str):
            return StringInterpolation.from_components(self.literals[:-1] + (self.literals[-1] + other,),
                                                       self.placeholders)
        if isinstance(other, Placeholder):
            return StringInterpolation.from_components(self.literals + ('',), self.placeholders + (other,))
        if isinstance(other, StringInterpolation):
            return StringInterpolation.from_components(
                self.literals[:-1] + (self.literals[-1] + other.literals[0],) + other.literals[1:],
                self.placeholders + other.placeholders
            )
        return NotImplemented

    def __radd__(self, other: object) -> 'StringInterpolation':
        if isinstance(other, str):
            return StringInterpolation.from_components((other + self.literals[0],) + self.literals[1:],
                                                       self.placeholders)
        return NotImplemented

    def __mod__(self, substitutions: 'Mapping[str, object]') -> 'StringInterpolation':
        """Substitute the placeholders in this :class:`StringInterpolation` object with string values (if possible)
        according to the ``substitutions`` mapping.

        >>> StringInterpolation('prefix ', Placeholder('data'), ' suffix') % {'data': 'hello'}
        StringInterpolation('prefix hello suffix')

        Args:
            substitutions: a mapping from placeholder names to the values to be filled in; all values
                are converted into :obj:`str`

        Returns:
            a new :class:`StringInterpolation` object with as many placeholders substituted as possible

        """
        result = StringInterpolation()
        for component in self.iter_components():
            if isinstance(component, Placeholder) and component.name in substitutions:
                result += str(substitutions[component.name])
            else:
                result += component
        return result

    @property
    def result(self) -> str:
        """Alias of :meth:`StringInterpolation.__str__` to get the fully-substituted string interpolation result.

        >>> StringInterpolation('prefix hello suffix').result
        'prefix hello suffix'

        """
        return str(self)


class BPCInternalError(RuntimeError):
    """Internal bug happened in BPC tools."""

    def __init__(self, message: object, context: str):
        """Initialize BPCInternalError.

        Args:
            message: the error message
            context: describe the context/location/component where the bug happened

        Raises:
            TypeError: if ``context`` is not :obj:`str`
            ValueError: if ``message`` (when converted to :obj:`str`) or ``context`` is empty or
                only contains whitespace characters

        """
        msg_string = str(message)
        if not msg_string.strip():
            raise ValueError('message should not be empty')
        if not isinstance(context, str):
            raise TypeError('context should be str')
        if not context.strip():
            raise ValueError('context should not be empty')
        super().__init__(textwrap.dedent('''\
            An internal bug happened in {}:

            {}

            Please report this error to project maintainers.''').format(context, msg_string))


__all__ = ['first_truthy', 'first_non_none', 'UUID4Generator', 'Config', 'Placeholder', 'StringInterpolation',
           'BPCInternalError']
