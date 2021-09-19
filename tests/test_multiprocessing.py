import os
import re
import shutil
import subprocess  # nosec
import sys
import textwrap

import pytest

from bpc_utils import Config, TaskLock, map_tasks
from bpc_utils.multiprocessing import _mp_map_wrapper, parallel_available
from bpc_utils.typing import TYPE_CHECKING

from .testutils import write_text_file

if TYPE_CHECKING:
    from pathlib import Path  # isort: split
    from bpc_utils.typing import Callable, Iterable, List, Mapping, Optional, T, Tuple  # isort: split
    from .testutils import CaptureFixture, MonkeyPatch


def square(x: int) -> int:
    return x ** 2


def lock_user_multiple_times(x: int) -> int:
    for i in range(100):
        with TaskLock():
            if i & 1:
                x += 1
            else:
                x -= 1
    return x


@pytest.mark.parametrize(
    'args,result',
    [
        ((square, (6,), {}), 36),
        ((square, range(6, 7), {}), 36),
        ((int, ('0x10',), {'base': 16}), 16),
        ((int, ('0x10',), Config(base=16)), 16),
    ]
)
def test__mp_map_wrapper(args: 'Tuple[Callable[..., T], Iterable[object], Mapping[str, object]]', result: 'T') -> None:
    assert _mp_map_wrapper(args) == result


@pytest.mark.parametrize(
    'func,iterable,posargs,kwargs,result',
    [
        (square, [1, 2, 3], None, None, [1, 4, 9]),
        (square, range(1, 4), None, None, [1, 4, 9]),
        (divmod, [4, 7, 9], (3,), None, [(1, 1), (2, 1), (3, 0)]),
        (int, ['0x%c' % c for c in 'abc'], None, {'base': 0}, [10, 11, 12]),
        (max, [4, -7, 9], range(6, 7), Config(key=abs), [6, -7, 9]),
    ]
)
@pytest.mark.parametrize('processes', [None, 1, 2])
@pytest.mark.parametrize('chunksize', [None, 2])
@pytest.mark.parametrize('parallel', [True, False])
def test_map_tasks(func: 'Callable[..., T]', iterable: 'Iterable[object]', posargs: 'Optional[Iterable[object]]',
                   kwargs: 'Optional[Mapping[str, object]]', processes: 'Optional[int]', chunksize: 'Optional[int]',
                   parallel: bool, result: 'List[T]', monkeypatch: 'MonkeyPatch') -> None:
    # test both under normal condition and when parallel execution is not available
    if not parallel:
        monkeypatch.setattr(sys.modules['bpc_utils.multiprocessing'], 'parallel_available', False)
    assert map_tasks(func, iterable, posargs=posargs, kwargs=kwargs,
                     processes=processes, chunksize=chunksize) == result


def test_lock(tmp_path: 'Path', monkeypatch: 'MonkeyPatch', capfd: 'CaptureFixture[str]') -> None:
    with TaskLock():
        pass

    num_tasks = 10
    num_print = 1000
    code_template = textwrap.dedent("""\
        from bpc_utils import TaskLock, map_tasks


        def task(task_id):
            {context1}
                for i in range({num_print}):
                    {context2}
                        print('Task %d says %d' % (task_id, i), flush=True)


        if __name__ == '__main__':
            map_tasks(task, range({num_tasks}))
    """)
    context_no_lock = 'for _ in [0]:'
    context_with_lock = 'with TaskLock():'
    code_interleave = code_template.format(context1=context_no_lock, context2=context_with_lock,
                                           num_print=num_print, num_tasks=num_tasks)
    code_no_interleave = code_template.format(context1=context_with_lock, context2=context_no_lock,
                                              num_print=num_print, num_tasks=num_tasks)

    def has_interleave(output: str) -> bool:
        records = re.findall(r'Task (\d+) says (\d+)', output)  # type: List[Tuple[str, str]]
        task_events = [[] for _ in range(num_tasks)]  # type: List[List[Tuple[int, int]]]
        for i, r in enumerate(records):
            task_events[int(r[0])].append((i, int(r[1])))
        for i in range(num_tasks):
            if [ev[1] for ev in task_events[i]] != list(range(num_print)):  # pragma: no cover
                raise ValueError('task %d prints incorrectly' % i)
        for i in range(num_tasks):
            start = task_events[i][0][0]
            if [ev[0] for ev in task_events[i]] != list(range(start, start + num_print)):
                return True
        return False

    monkeypatch.chdir(tmp_path)
    shutil.copytree(os.path.dirname(sys.modules['bpc_utils'].__file__), 'bpc_utils')
    test_filename = 'test_lock.py'

    write_text_file(test_filename, code_interleave)
    subprocess.check_call([sys.executable, '-u', test_filename])  # nosec
    captured = capfd.readouterr()
    # Note: There is actually a small possibility that execution of multiple processes does not interleave.
    assert has_interleave(captured.out) == parallel_available
    assert not captured.err

    write_text_file(test_filename, code_no_interleave)
    subprocess.check_call([sys.executable, '-u', test_filename])  # nosec
    captured = capfd.readouterr()
    assert not has_interleave(captured.out)
    assert not captured.err


@pytest.mark.parametrize('parallel', [True, False])
def test_lock_use_multiple_times(parallel: bool, monkeypatch: 'MonkeyPatch') -> None:
    # test both under normal condition and when parallel execution is not available
    if not parallel:
        monkeypatch.setattr(sys.modules['bpc_utils.multiprocessing'], 'parallel_available', False)
    assert map_tasks(lock_user_multiple_times, range(32)) == list(range(32))
