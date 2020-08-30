"""BPC conversion context."""

import abc

from .misc import UUID4Generator


class BaseContext(abc.ABC):
    """Abstract base class for general conversion context."""

    def __init__(self, node, config, *, indent_level=0, raw=False):
        """Initialize BaseContext.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST
            config (Config): conversion configurations

        Keyword Args:
            indent_level (int): current indentation level
            raw (bool): raw processing flag

        """
        #: Config: Internal configurations.
        self.config = config
        #: str: Indentation sequence.
        self._indentation = config.indentation
        #: Literal['\\n', '\\r\\n', '\\r']: Line seperator.
        self._linesep = config.linesep
        #: bool: :pep:`8` compliant conversion flag.
        self._pep8 = config.pep8

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

    def __iadd__(self, code):
        """Support of the ``+=`` operator.

        If :attr:`self._prefix_or_suffix <bpc_utils.BaseContext._prefix_or_suffix>` is :data:`True`,
        then the ``code`` will be appended to :attr:`self._prefix <bpc_utils.BaseContext._prefix>`;
        else it will be appended to :attr:`self._suffix <bpc_utils.BaseContext._suffix>`.

        Args:
            code (str): code string

        Returns:
            BaseContext: self

        """
        if self._prefix_or_suffix:
            self._prefix += code
        else:
            self._suffix += code
        return self

    def __str__(self):
        """Returns a *stripped* version of :attr:`self._buffer <bpc_utils.BaseContext._buffer>`."""
        return self._buffer.strip()

    @property
    def string(self):
        """Returns conversion buffer (:attr:`self._buffer <bpc_utils.BaseContext._buffer>`)."""
        return self._buffer

    def _walk(self, node):
        """Start traversing the AST module.

        The method traverses through all *children* of ``node``. It first checks
        if such child has the target expression. If so, it will toggle
        :attr:`self._prefix_or_suffix <bpc_utils.BaseContext._prefix_or_suffix>`
        (set to :data:`False`) and save the last previous child as
        :attr:`self._node_before_expr <bpc_utils.BaseContext._node_before_expr>`.
        Then it processes the child with :meth:`self._process <bpc_utils.BaseContext._process>`.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        """
        # process node
        if hasattr(node, 'children'):
            last_node = None
            for child in node.children:
                if self.has_expr(child):
                    self._prefix_or_suffix = False
                    self._node_before_expr = last_node
                self._process(child)
                last_node = child
            return

        # preserve leaf node as is by default
        self += node.get_code()

    def _process(self, node):
        """Recursively process parso AST.

        All processing methods for a specific ``node`` type are defined as
        ``_process_{type}``. This method first checks if such processing
        method exists. If so, it will call such method on the ``node``;
        otherwise it will traverse through all *children* of ``node``, and perform
        the same logic on each child.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        """
        func_name = '_process_%s' % node.type
        if hasattr(self, func_name):
            func = getattr(self, func_name)
            func(node)
            return

        if hasattr(node, 'children'):
            for child in node.children:
                self._process(child)
            return

        # preserve leaf node as is by default
        self += node.get_code()

    @abc.abstractmethod
    def _concat(self):
        """Concatenate final string."""
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def has_expr(self, node):
        """Check if node has the target expression.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        Returns:
            bool: if ``node`` has the target expression

        """
        raise NotImplementedError  # pragma: no cover

    @staticmethod
    def split_comments(code, linesep):
        """Separates prefixing comments from code.

        This method separates *prefixing* comments and *suffixing* code. It is
        rather useful when inserting code might break `shebang`_ and encoding
        cookies (:pep:`263`), etc.

        .. _shebang: https://en.wikipedia.org/wiki/Shebang_(Unix)

        Args:
            code (str): the code to split comments
            linesep (str): line seperator

        Returns:
            Tuple[str, str]: a tuple of *prefix comments* and *suffix code*

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
    def missing_newlines(prefix, suffix, expected, linesep):
        """Count missing blank lines for code insertion given surrounding code.

        Args:
            prefix (str): preceding source code
            suffix (str): succeeding source code
            expected (int): number of expected blank lines
            linesep (str): line seperator

        Returns:
            int: number of blank lines to add

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
    def extract_whitespaces(node):
        """Extract preceding and succeeding whitespaces from the node given.

        Args:
            node (parso.tree.NodeOrLeaf) parso AST

        Returns:
            Tuple[str, str]: a tuple of *preceding* and *succeeding* whitespaces in ``node``

        """
        code = node.get_code()

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


__all__ = ['BaseContext']
