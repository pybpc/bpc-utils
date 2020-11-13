# pylint: disable=unused-import

"""Type annotations for this package."""
import os
import re
import sys
from typing import (Callable, Dict, Generator, Iterable, Iterator, List, Mapping, Optional, Set,
                    TextIO, Tuple, TypeVar, Union, cast)

from typing_extensions import ContextManager, Deque, Final, Literal, Type, final, overload

# isort: off

T = TypeVar('T')
Linesep = Literal['\n', '\r\n', '\r']

# If running Sphinx build, set :data:`typing.TYPE_CHECKING` to :data:`True`.
# This is a workaround because module import happens before sphinx-autodoc-typehints gains control.
if re.fullmatch(r'(?ai)sphinx-build(?:\.exe)?', os.path.basename(sys.argv[0])):
    import typing
    import typing_extensions
    typing.TYPE_CHECKING = True  # novermin
    typing_extensions.TYPE_CHECKING = True

from typing_extensions import TYPE_CHECKING  # noqa: E402  # pylint: disable=wrong-import-position

__all__ = ['Linesep']
