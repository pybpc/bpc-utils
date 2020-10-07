# pylint: disable=unused-import

"""Type annotations for this package."""

from typing import (Callable, Dict, Generator, Iterable, Iterator, List, Mapping, Optional, Set,
                    TextIO, Tuple, TypeVar, Union, cast)

from typing_extensions import ContextManager, Deque, Final, Literal, Type, overload

T = TypeVar('T')
Linesep = Literal['\n', '\r\n', '\r']

__all__ = ['Linesep']
