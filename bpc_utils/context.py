"""BPC conversion context."""

import abc
import unicodedata

import parso

from .misc import Config, UUID4Generator
from .typing import Callable, Linesep, Tuple, TypeVar

BaseContextType = TypeVar('BaseContextType', bound='BaseContext')


class BaseContext(abc.ABC):
    """Abstract base class for general conversion context."""

    def __init__(self, node: parso.tree.NodeOrLeaf, config: Config, *,
                 indent_level: int = 0, raw: bool = False) -> None:
        """Initialize BaseContext.

        Args:
            node: parso AST
            config (:class:`~bpc_utils.Config`): conversion configurations
            indent_level: current indentation level
            raw: raw processing flag

        """
        #: :class:`~bpc_utils.Config`: Internal configurations.
        self.config = config
        #: str: Indentation sequence.
        self._indentation = config.indentation  # type: str # type: ignore[attr-defined]
        #: :data:`~bpc_utils.Linesep`: Line seperator.
        self._linesep = config.linesep  # type: Linesep # type: ignore[attr-defined]
        #: bool: :pep:`8` compliant conversion flag.
        self._pep8 = config.pep8  # type: bool  # type: ignore[attr-defined]

        #: parso.tree.NodeOrLeaf: Root node given by the ``node`` parameter.
        self._root = node
        #: int: Current indentation level.
        self._indent_level = indent_level

        #: UUID4Generator: UUID generator.
        self._uuid_gen = UUID4Generator(dash=False)

        #: str: Code before insertion point.
        self._prefix = ''
        #: str: Code after insertion point.
        self._suffix = ''
        #: str: Final converted result.
        self._buffer = ''

        #: bool: Flag if buffer is now :attr:`self._prefix <bpc_utils.BaseContext._prefix>`.
        self._prefix_or_suffix = True
        #: Optional[parso.tree.NodeOrLeaf]: Preceding node with the target expression, i.e. the *insertion point*.
        self._node_before_expr = None

        self._walk(node)  # traverse children

        if raw:
            self._buffer = self._prefix + self._suffix
        else:
            self._concat()  # generate final result

    def __iadd__(self: BaseContextType, code: str) -> BaseContextType:
        """Support of the ``+=`` operator.

        If :attr:`self._prefix_or_suffix <bpc_utils.BaseContext._prefix_or_suffix>` is :data:`True`,
        then the ``code`` will be appended to :attr:`self._prefix <bpc_utils.BaseContext._prefix>`;
        else it will be appended to :attr:`self._suffix <bpc_utils.BaseContext._suffix>`.

        Args:
            code: code string

        Returns:
            BaseContext: self

        """
        if self._prefix_or_suffix:
            self._prefix += code
        else:
            self._suffix += code
        return self

    def __str__(self) -> str:
        """Returns a *stripped* version of :attr:`self._buffer <bpc_utils.BaseContext._buffer>`."""
        return self._buffer.strip()

    @property
    def string(self) -> str:
        """Returns conversion buffer (:attr:`self._buffer <bpc_utils.BaseContext._buffer>`)."""
        return self._buffer

    def _walk(self, node: parso.tree.NodeOrLeaf) -> None:
        """Start traversing the AST module.

        The method traverses through all *children* of ``node``. It first checks
        if such child has the target expression. If so, it will toggle
        :attr:`self._prefix_or_suffix <bpc_utils.BaseContext._prefix_or_suffix>`
        (set to :data:`False`) and save the last previous child as
        :attr:`self._node_before_expr <bpc_utils.BaseContext._node_before_expr>`.
        Then it processes the child with :meth:`self._process <bpc_utils.BaseContext._process>`.

        Args:
            node: parso AST

        """
        # process node
        if hasattr(node, 'children'):
            last_node = None
            for child in node.children:  # type: ignore[attr-defined]
                if self._prefix_or_suffix and self.has_expr(child):
                    self._prefix_or_suffix = False
                    self._node_before_expr = last_node
                self._process(child)
                last_node = child
            return

        # preserve leaf node as is by default
        self += node.get_code()

    def _process(self, node: parso.tree.NodeOrLeaf) -> None:
        """Recursively process parso AST.

        All processing methods for a specific ``node`` type are defined as
        ``_process_{type}``. This method first checks if such processing
        method exists. If so, it will call such method on the ``node``;
        otherwise it will traverse through all *children* of ``node``, and perform
        the same logic on each child.

        Args:
            node: parso AST

        """
        func_name = '_process_%s' % node.type
        if hasattr(self, func_name):
            func = getattr(self, func_name)  # type: Callable[[parso.tree.NodeOrLeaf], None]
            func(node)
            return

        if hasattr(node, 'children'):
            for child in node.children:  # type: ignore[attr-defined]
                self._process(child)
            return

        # preserve leaf node as is by default
        self += node.get_code()

    @abc.abstractmethod
    def _concat(self) -> None:
        """Concatenate final string."""
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def has_expr(self, node: parso.tree.NodeOrLeaf) -> bool:
        """Check if node has the target expression.

        Args:
            node: parso AST

        Returns:
            whether ``node`` has the target expression

        """
        raise NotImplementedError  # pragma: no cover

    @staticmethod
    def split_comments(code: str, linesep: Linesep) -> Tuple[str, str]:
        """Separates prefixing comments from code.

        This method separates *prefixing* comments and *suffixing* code. It is
        rather useful when inserting code might break `shebang`_ and encoding
        cookies (:pep:`263`), etc.

        .. _shebang: https://en.wikipedia.org/wiki/Shebang_(Unix)

        Args:
            code: the code to split comments
            linesep (:data:`~bpc_utils.Linesep`): line seperator

        Returns:
            a tuple of *prefix comments* and *suffix code*

        """
        prefix = ''
        suffix = ''
        prefix_or_suffix = True

        for line in code.split(linesep):
            if prefix_or_suffix:
                if line.strip().startswith('#'):
                    prefix += line + linesep
                    continue
                prefix_or_suffix = False
            suffix += line + linesep

        if prefix_or_suffix:
            prefix = prefix[:-len(linesep)]  # 3.9+ str.removesuffix
        else:
            suffix = suffix[:-len(linesep)]

        return prefix, suffix

    @staticmethod
    def missing_newlines(prefix: str, suffix: str, expected: int, linesep: Linesep) -> int:
        """Count missing blank lines for code insertion given surrounding code.

        Args:
            prefix: preceding source code
            suffix: succeeding source code
            expected: number of expected blank lines
            linesep (:data:`~bpc_utils.Linesep`): line seperator

        Returns:
            number of blank lines to add

        """
        current = 0

        # count trailing newlines in `prefix`
        if prefix:
            for line in reversed(prefix.split(linesep)):  # pragma: no branch
                if line.strip():
                    break
                current += 1
            if current > 0:  # keep a trailing newline in `prefix`
                current -= 1

        # count leading newlines in `suffix`
        if suffix:
            for line in suffix.split(linesep):  # pragma: no branch
                if line.strip():
                    break
                current += 1

        missing = expected - current
        return max(missing, 0)

    @staticmethod
    def extract_whitespaces(code: str) -> Tuple[str, str]:
        """Extract preceding and succeeding whitespaces from the code given.

        Args:
            code: the code to extract whitespaces

        Returns:
            a tuple of *preceding* and *succeeding* whitespaces in ``code``

        """
        # get preceding whitespaces
        prefix = ''
        for char in code:
            if char not in ' \t\n\r\f':
                break
            prefix += char

        # get succeeding whitespaces
        suffix = ''
        for char in reversed(code):
            if char not in ' \t\n\r\f':
                break
            suffix += char

        return prefix, suffix[::-1]

    @staticmethod
    def normalize(name: str) -> str:
        """Normalize variable names.

        The method normalizes variable names as described in `Python documentation`_
        and :pep:`3131`.

        Args:
            name (str): variable name

        Returns:
            str: normalized variable name

        .. Python documentation: https://docs.python.org/3/reference/lexical_analysis.html#identifiers

        """
        return unicodedata.normalize('NFKC', name)

    @classmethod
    def mangle(cls, cls_name: str, var_name: str) -> str:
        """Mangle variable names.

        The method mangles variable names as described in `Python documentation`_
        and further normalizes the mangled variable name through
        :meth:`~bpc_utils.context.Context.normalize`.

        Args:
            cls_name (str): class name
            var_name (str): variable name

        Returns:
            str: mangled variable name

        .. _Python documentation: https://docs.python.org/3/reference/expressions.html#atom-identifiers

        """
        # should only perform mangling if variable name begins with two or more underscores
        # and does not end in two or more underscores
        if not var_name.startswith('__') or var_name.endswith('__'):
            name = var_name
        # perform mangling, remove leading underscores from the class name when inserting
        else:
            name = '_%(cls)s%(var)s' % dict(cls=cls_name.lstrip('_'), var=var_name)
        return cls.normalize(name)


__all__ = ['BaseContext']
