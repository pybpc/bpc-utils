"""Miscellaneous utilities."""

import collections.abc
import io
import keyword
import platform
import uuid

is_windows = platform.system() == 'Windows'


def first_truthy(*args):
    """Return the first *truthy* value from a list of values.

    Args:
        *args: variable length argument list

            * If one positional argument is provided, it should be an iterable of the values.
            * If two or more positional arguments are provided, then the value list is the positional argument list.

    Returns:
        Any: the first *truthy* value, if no *truthy* values found or sequence is empty, return :data:`None`

    Raises:
        TypeError: if no arguments provided

    """
    if not args:
        raise TypeError('no arguments provided')
    if len(args) == 1:
        args = args[0]
    return next(filter(bool, args), None)  # pylint: disable=filter-builtin-not-iterating


def first_non_none(*args):
    """Return the first non-:data:`None` value from a list of values.

    Args:
        *args: variable length argument list

            * If one positional argument is provided, it should be an iterable of the values.
            * If two or more positional arguments are provided, then the value list is the positional argument list.

    Returns:
        Any: the first non-:data:`None` value, if all values are :data:`None` or sequence is empty, return :data:`None`

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


class MakeTextIO:
    """Context wrapper class to handle :obj:`str` and *file* objects together.

    Attributes:
        obj (Union[str, TextIO]): the object to manage in the context
        sio (Optional[StringIO]): the I/O object to manage in the context
            only if :attr:`self.obj <MakeTextIO.obj>` is :obj:`str`
        pos (Optional[int]): the original offset of :attr:`self.obj <MakeTextIO.obj>`,
            only if :attr:`self.obj <MakeTextIO.obj>` is a seekable *file* object

    """

    def __init__(self, obj):
        """Initialize context.

        Args:
            obj (Union[str, TextIO]): the object to manage in the context

        """
        self.obj = obj

    def __enter__(self):
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

    def __exit__(self, exc_type, exc_value, traceback):
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

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __contains__(self, key):
        return key in self.__dict__

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        del self.__dict__[key]

    def __eq__(self, other):
        return isinstance(other, Config) and self.__dict__ == other.__dict__

    def __repr__(self):
        type_name = type(self).__name__
        arg_strings = []
        star_args = {}
        for name, value in sorted(self.__dict__.items()):
            if name.isidentifier() and not keyword.iskeyword(name) and name != '__debug__':
                arg_strings.append('%s=%r' % (name, value))
            else:  # wrap invalid names into a dict to make __repr__ round-trip
                star_args[name] = value
        if star_args:
            arg_strings.append('**%s' % repr(star_args))
        return '%s(%s)' % (type_name, ', '.join(arg_strings))


__all__ = ['first_truthy', 'first_non_none', 'UUID4Generator', 'Config']
