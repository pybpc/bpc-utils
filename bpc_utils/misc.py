"""Miscellaneous utilities."""

import collections.abc
import io
import keyword
import platform
import types
import uuid

from .typing import Dict, Iterable, Iterator, List, Optional, Set, T, TextIO, Type, Union, overload

is_windows = platform.system() == 'Windows'


@overload
def first_truthy(*args: T) -> Optional[T]:
    ...


@overload
def first_truthy(args: Iterable[T]) -> Optional[T]:  # noqa: F811
    ...


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
def first_non_none(*args: T) -> Optional[T]:
    ...


@overload
def first_non_none(args: Iterable[T]) -> Optional[T]:  # noqa: F811
    ...


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

    def __init__(self, obj: Union[str, TextIO]) -> None:
        """Initialize context.

        Args:
            obj: the object to manage in the context

        """
        self.obj = obj

    def __enter__(self) -> TextIO:
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
            self.sio = io.StringIO(self.obj, newline='')  # turn off newline translation # pylint: disable=W0201
            return self.sio
        if self.obj.seekable():
            #: int: the original offset of :attr:`self.obj <MakeTextIO.obj>`,
            #: only if :attr:`self.obj <MakeTextIO.obj>` is a seekable
            #: :class:`TextIO <io.TextIOWrapper>`
            self.pos = self.obj.tell()  # pylint: disable=W0201
            #: Union[str, TextIO]: the object to manage in the context
            self.obj.seek(0)
        return self.obj

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
                 traceback: Optional[types.TracebackType]) -> None:
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


class Config(collections.abc.MutableMapping):
    """Configuration namespace.

    This class is inspired from :class:`argparse.Namespace` for storing
    internal attributes and/or configuration variables.

    """

    def __init__(self, **kwargs: object) -> None:
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __contains__(self, key: object) -> bool:
        return key in self.__dict__

    def __iter__(self) -> Iterator[str]:
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


__all__ = ['first_truthy', 'first_non_none', 'UUID4Generator', 'Config']
