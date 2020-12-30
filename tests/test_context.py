import ast

import pytest

from bpc_utils import BaseContext, Config, UUID4Generator, parso_parse
from bpc_utils.typing import TYPE_CHECKING

if TYPE_CHECKING:
    import parso  # isort: split
    from bpc_utils import Linesep  # pylint: disable=ungrouped-imports
    from bpc_utils.typing import Tuple  # pylint: disable=ungrouped-imports


class MagicContext(BaseContext):
    """A test context class with abstract methods implemented."""

    def _concat(self) -> None:
        self._buffer = self._prefix + ' \u0200 ' + self._suffix

    def has_expr(self, node: 'parso.tree.NodeOrLeaf') -> bool:
        return 'magic' in node.get_code()

    def _process_number(self, node: 'parso.python.tree.Number') -> None:  # pylint: disable=no-self-use
        """Process number nodes.

        Args:
            node: a number node

        """
        node.value = repr(ast.literal_eval(node.value) + 666)
        self += node.get_code()

    def _process_string(self, node: 'parso.python.tree.String') -> None:  # pylint: disable=no-self-use
        """Process string nodes.

        Args:
            node: a string node

        """
        node.value = repr(ast.literal_eval(node.value) + 'nb')
        self += node.get_code()


def test_BaseContext() -> None:
    test_code = 'test = 123; "test"; test = "test", 123'
    converted_result = "test = 789; 'testnb'; test = 'testnb', 789"
    node = parso_parse(test_code)
    config = Config(
        indentation='\t',
        linesep='\n',
        pep8=True,
    )

    context = MagicContext(node, config)
    assert context.config == config
    assert context._indentation == '\t'  # pylint: disable=protected-access
    assert context._linesep == '\n'  # pylint: disable=protected-access
    assert context._pep8 is True  # pylint: disable=protected-access
    assert context._root is node  # pylint: disable=protected-access
    assert context._indent_level == 0  # pylint: disable=protected-access
    assert isinstance(context._uuid_gen, UUID4Generator)  # pylint: disable=protected-access
    assert context.string == converted_result + ' \u0200 '
    assert str(context) == converted_result + ' \u0200'

    context = MagicContext(parso_parse(test_code), config, raw=True)
    assert context.string == converted_result

    # "magic" should go into suffix
    context = MagicContext(parso_parse('magic'), config)
    assert context.string == ' \u0200 magic'

    # test passing a leaf node to BaseContext
    context = MagicContext(parso_parse('123').children[0], config)
    assert context.string == '123 \u0200 '


@pytest.mark.parametrize(
    'code,linesep,result',
    [
        ('print(666)', '\n', ('', 'print(666)')),
        ('# comment\nprint(666)', '\n', ('# comment\n', 'print(666)')),
        ('# comment\nprint(666)', '\r', ('# comment\nprint(666)', '')),
        ('# comment\rprint(666)\r', '\r', ('# comment\r', 'print(666)\r')),
        ('# c1\n #c2\nprint(666)\n', '\n', ('# c1\n #c2\n', 'print(666)\n')),
        ('# coding: gbk\n \n# comment\nprint(666)\n', '\n', ('# coding: gbk\n', ' \n# comment\nprint(666)\n')),
    ]
)
def test_BaseContext_split_comments(code: str, linesep: 'Linesep', result: 'Tuple[str, str]') -> None:
    assert BaseContext.split_comments(code, linesep) == result


@pytest.mark.parametrize(
    'prefix,suffix,expected,linesep,result',
    [
        ('test', 'test', 2, '\n', 2),
        ('test\n', 'test', 2, '\n', 2),
        ('test', '\ntest', 2, '\n', 1),
        ('test\n\n', 'test', 2, '\n', 1),
        ('test\n\n', '\ntest', 2, '\n', 0),
        ('test\n', '\n\ntest', 2, '\n', 0),
        ('test', '\rtest', 2, '\n', 2),
        ('test', '\ntest', 2, '\r\n', 2),
        ('test', '', 2, '\n', 2),
        ('', 'test', 2, '\n', 2),
        ('', '', 2, '\n', 2),
    ]
)
def test_BaseContext_missing_newlines(prefix: str, suffix: str, expected: int, linesep: 'Linesep', result: int) -> None:
    assert BaseContext.missing_newlines(prefix, suffix, expected, linesep) == result


@pytest.mark.parametrize(
    'code,result',
    [
        ('\ntest = "test", 123, "test", 123   ', ('\n', '   ')),
        ('\rtest = "test", 123, "test", 123\f\t', ('\r', '\f\t')),
        ('test = "test", 123, "test", 123\t', ('', '\t')),
        ('\r\ntest = "test", 123, "test", 123', ('\r\n', '')),
        ('test = 1', ('', '')),
        ('', ('', '')),
    ]
)
def test_BaseContext_extract_whitespaces(code: str, result: 'Tuple[str, str]') -> None:
    assert BaseContext.extract_whitespaces(code) == result


@pytest.mark.parametrize(
    'name,result',
    [
        ('A', 'A'),
        ('__x', '__x'),
        ('\u4e2d\u6587', '\u4e2d\u6587'),
        ('__\u4e2d\u6587', '__\u4e2d\u6587'),
        ('\u0043\u0327', '\u00c7'),
        ('__\u0043\u0327', '__\u00c7'),
    ]
)
def test_BaseContext_normalize(name: str, result: str) -> None:
    assert BaseContext.normalize(name) == result


@pytest.mark.parametrize('cls_name', ['Foo', '_Foo', '__Foo'])
@pytest.mark.parametrize(
    'var_name,result',
    [
        ('__x', '_Foo__x'),
        ('__x_', '_Foo__x_'),
        ('__\u0043\u0327', '_Foo__\u00c7'),
        ('__\u0043\u0327_', '_Foo__\u00c7_'),
    ]
)
def test_BaseContext_mangle_var_name(cls_name: str, var_name: str, result: str) -> None:
    assert BaseContext.mangle(cls_name, var_name) == result


@pytest.mark.parametrize('cls_name', ['\u0044\u0327_', '_\u0044\u0327_', '__\u0044\u0327_'])
@pytest.mark.parametrize(
    'var_name,result',
    [
        ('__x', '_\u1e10___x'),
        ('__x_', '_\u1e10___x_'),
        ('__\u0043\u0327', '_\u1e10___\u00c7'),
        ('__\u0043\u0327_', '_\u1e10___\u00c7_'),
    ]
)
def test_BaseContext_mangle_class_name(cls_name: str, var_name: str, result: str) -> None:
    assert BaseContext.mangle(cls_name, var_name) == result


@pytest.mark.parametrize('cls_name', ['Foo', '_Foo', '__Foo', '_', '__'])
@pytest.mark.parametrize(
    'var_name,result',
    [
        ('\u0043\u0327', '\u00c7'),
        ('_\u0043\u0327', '_\u00c7'),
        ('__\u0043\u0327__', '__\u00c7__'),
    ]
)
def test_BaseContext_mangle_normalize_only_var(cls_name: str, var_name: str, result: str) -> None:
    assert BaseContext.mangle(cls_name, var_name) == result


@pytest.mark.parametrize('cls_name', ['_', '__', '___'])
@pytest.mark.parametrize(
    'var_name,result',
    [
        ('__\u0043\u0327', '__\u00c7'),
        ('__\u0043\u0327_', '__\u00c7_'),
    ]
)
def test_BaseContext_mangle_normalize_only_class(cls_name: str, var_name: str, result: str) -> None:
    assert BaseContext.mangle(cls_name, var_name) == result


@pytest.mark.parametrize('cls_name', ['Foo', '_Foo', '__Foo', '_', '__'])
@pytest.mark.parametrize('var_name', ['x', '_x', '__x__', '__x___'])
def test_BaseContext_mangle_should_not_alter_var(cls_name: str, var_name: str) -> None:
    assert BaseContext.mangle(cls_name, var_name) == var_name


@pytest.mark.parametrize('cls_name', ['_', '__', '___'])
@pytest.mark.parametrize('var_name', ['__x', '__x_'])
def test_BaseContext_mangle_should_not_alter_class(cls_name: str, var_name: str) -> None:
    assert BaseContext.mangle(cls_name, var_name) == var_name
