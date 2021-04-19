"""Parallel execution support for BPC."""

import os

from .misc import nullcontext
from .typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType  # isort: split
    from .typing import Callable, ContextManager, Iterable, List, Mapping, Optional, T, Tuple

# multiprocessing support detection and CPU_CNT retrieval
try:        # try first
    import multiprocessing
except ImportError:  # pragma: no cover
    multiprocessing = None  # type: ignore[assignment]
else:       # CPU number if multiprocessing supported
    if os.name == 'posix' and 'SC_NPROCESSORS_CONF' in getattr(os, 'sysconf_names'):  # pragma: no cover
        CPU_CNT = getattr(os, 'sysconf')('SC_NPROCESSORS_CONF')
    elif hasattr(os, 'sched_getaffinity'):  # pragma: no cover
        CPU_CNT = len(getattr(os, 'sched_getaffinity')(0))
    else:  # pragma: no cover
        CPU_CNT = os.cpu_count() or 1
finally:    # alias and aftermath
    mp = multiprocessing  # type: Optional[ModuleType]
    del multiprocessing

parallel_available = mp is not None and CPU_CNT > 1


def _mp_map_wrapper(args: 'Tuple[Callable[..., T], Iterable[object], Mapping[str, object]]') -> 'T':
    """Map wrapper function for :mod:`multiprocessing`.

    Args:
        args: the function to execute, the positional arguments and the keyword arguments packed into a tuple

    Returns:
        the function execution result

    """
    func, posargs, kwargs = args
    return func(*posargs, **kwargs)


def _mp_init_lock(lock: 'ContextManager[None]') -> None:  # pragma: no cover
    """Initialize lock for :mod:`multiprocessing`.

    Args:
        lock: the lock to be shared among tasks

    """
    global task_lock  # pylint: disable=global-statement
    task_lock = lock


def map_tasks(func: 'Callable[..., T]', iterable: 'Iterable[object]', posargs: 'Optional[Iterable[object]]' = None,
              kwargs: 'Optional[Mapping[str, object]]' = None, *,
              processes: 'Optional[int]' = None, chunksize: 'Optional[int]' = None) -> 'List[T]':
    """Execute tasks in parallel if :mod:`multiprocessing` is available, otherwise execute them sequentially.

    Args:
        func: the task function to execute
        iterable: the items to process
        posargs: additional positional arguments to pass to ``func``
        kwargs: keyword arguments to pass to ``func``
        processes: the number of worker processes (default: auto determine)
        chunksize: chunk size for multiprocessing

    Returns:
        the return values of the task function applied on the input items and additional arguments

    """
    global task_lock  # pylint: disable=global-statement

    if posargs is None:
        posargs = ()
    if kwargs is None:
        kwargs = {}

    # sequential execution
    if not parallel_available or processes == 1:
        return [func(item, *posargs, **kwargs) for item in iterable]

    # parallel execution
    processes = processes or CPU_CNT
    lock = mp.Lock()  # type: ignore[union-attr]
    with mp.Pool(processes=processes, initializer=_mp_init_lock, initargs=(lock,)) as pool:  # type: ignore[union-attr]
        result = pool.map(
            _mp_map_wrapper,
            [(func, (item,) + tuple(posargs), kwargs) for item in iterable],
            chunksize
        )  # type: List[T]
    task_lock = nullcontext()
    return result


task_lock = nullcontext()  # type: ContextManager[None]


def TaskLock() -> 'ContextManager[None]':
    """Function that returns a lock for possibly concurrent tasks.

    Returns:
        a lock for possibly concurrent tasks

    """
    return task_lock


__all__ = ['map_tasks', 'TaskLock']
