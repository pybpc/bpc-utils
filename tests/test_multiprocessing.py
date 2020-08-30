import os
import re
import shutil
import subprocess  # nosec
import sys
import textwrap

import pytest
from bpc_utils import Config, TaskLock, map_tasks
from bpc_utils.multiprocessing import _mp_map_wrapper, parallel_available

from . import write_text_file


def square(x):
    return x ** 2


@pytest.mark.parametrize(
    'args,result',
    [
        ((square, (6,), {}), 36),
        ((square, range(6, 7), {}), 36),  # pylint: disable=range-builtin-not-iterating
        ((int, ('0x10',), {'base': 16}), 16),
        ((int, ('0x10',), Config(base=16)), 16),
    ]
)
def test__mp_map_wrapper(args, result):
    assert _mp_map_wrapper(args) == result  # nosec


@pytest.mark.parametrize(
    'func,iterable,posargs,kwargs,result',
    [
        (square, [1, 2, 3], None, None, [1, 4, 9]),
        (square, range(1, 4), None, None, [1, 4, 9]),  # pylint: disable=range-builtin-not-iterating
        (divmod, [4, 7, 9], (3,), None, [(1, 1), (2, 1), (3, 0)]),
        (int, ['0x%c' % c for c in 'abc'], None, {'base': 0}, [10, 11, 12]),
        (max, [4, -7, 9], range(6, 7), Config(key=abs), [6, -7, 9]),  # pylint: disable=range-builtin-not-iterating
    ]
)
@pytest.mark.parametrize('processes', [None, 1, 2])
@pytest.mark.parametrize('chunksize', [None, 2])
@pytest.mark.parametrize('parallel', [True, False])
def test_map_tasks(func, iterable, posargs, kwargs, processes, chunksize, parallel, result, monkeypatch):
    # test both under normal condition and when parallel execution is not available
    if not parallel:
        monkeypatch.setattr(sys.modules['bpc_utils.multiprocessing'], 'parallel_available', False)
    assert map_tasks(func, iterable, posargs=posargs, kwargs=kwargs,  # nosec
                     processes=processes, chunksize=chunksize) == result


def test_lock(tmp_path, monkeypatch, capfd):
    with TaskLock():
        pass

    num_tasks = 10
    num_print = 1000
    code_template = textwrap.dedent("""\
        from bpc_utils import TaskLock, map_tasks


        def task(task_id):
            {context}
                for i in range({num_print}):
                    print('Task %d says %d' % (task_id, i), flush=True)


        if __name__ == '__main__':
            map_tasks(task, range({num_tasks}))
    """)
    code_no_lock = code_template.format(context='for _ in [0]:', num_print=num_print, num_tasks=num_tasks)
    code_with_lock = code_template.format(context='with TaskLock():', num_print=num_print, num_tasks=num_tasks)

    def has_interleave(output):
        records = re.findall(r'Task (\d+) says (\d+)', output)
        task_events = [[] for _ in range(num_tasks)]
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
    test_filename = 'test-lock.py'

    write_text_file(test_filename, code_no_lock)
    subprocess.check_call([sys.executable, '-u', test_filename])  # nosec
    captured = capfd.readouterr()
    assert has_interleave(captured.out) == parallel_available  # nosec
    assert not captured.err  # nosec

    write_text_file(test_filename, code_with_lock)
    subprocess.check_call([sys.executable, '-u', test_filename])  # nosec
    captured = capfd.readouterr()
    assert not has_interleave(captured.out)  # nosec
    assert not captured.err  # nosec
