"""Parallel execution support for BPC."""

import contextlib
import os

# multiprocessing support detection and CPU_CNT retrieval
try:        # try first
    import multiprocessing
except ImportError:  # pragma: no cover
    multiprocessing = None
else:       # CPU number if multiprocessing supported
    if os.name == 'posix' and 'SC_NPROCESSORS_CONF' in os.sysconf_names:  # pylint: disable=no-member # pragma: no cover
        CPU_CNT = os.sysconf('SC_NPROCESSORS_CONF')  # pylint: disable=no-member
    elif 'sched_getaffinity' in os.__all__:  # pragma: no cover
        CPU_CNT = len(os.sched_getaffinity(0))  # pylint: disable=no-member
    else:  # pragma: no cover
        CPU_CNT = os.cpu_count() or 1
finally:    # alias and aftermath
    mp = multiprocessing
    del multiprocessing

parallel_available = mp is not None and CPU_CNT > 1

try:
    from contextlib import nullcontext  # novermin
except ImportError:  # backport contextlib.nullcontext for Python < 3.7 # pragma: no cover
    @contextlib.contextmanager
    def nullcontext(enter_result=None):
        yield enter_result


def _mp_map_wrapper(args):
    """Map wrapper function for :mod:`multiprocessing`.

    Args:
        args (Tuple[Callable, Iterable[Any], Mapping[str, Any]]): the function to execute,
            the positional arguments and the keyword arguments packed into a tuple

    Returns:
        Any: the function execution result

    """
    func, posargs, kwargs = args
    return func(*posargs, **kwargs)


def _mp_init_lock(lock):  # pragma: no cover
    """Initialize lock for :mod:`multiprocessing`.

    Args:
        lock (multiprocessing.synchronize.Lock): the lock to be shared among tasks

    """
    global task_lock  # pylint: disable=global-statement
    task_lock = lock


def map_tasks(func, iterable, posargs=None, kwargs=None, *, processes=None, chunksize=None):
    """Execute tasks in parallel if :mod:`multiprocessing` is available, otherwise execute them sequentially.

    Args:
        func (Callable): the task function to execute
        iterable (Iterable[Any]): the items to process
        posargs (Optional[Iterable[Any]]): additional positional arguments to pass to ``func``
        kwargs (Optional[Mapping[str, Any]]): keyword arguments to pass to ``func``
        processes (Optional[int]): the number of worker processes (default: auto determine)
        chunksize (Optional[int]): chunk size for multiprocessing

    Returns:
        List[Any]: the return values of the task function applied on the input items and additional arguments

    """
    global task_lock  # pylint: disable=global-statement

    if posargs is None:
        posargs = ()
    if kwargs is None:
        kwargs = {}

    if not parallel_available or processes == 1:  # sequential execution
        return [func(item, *posargs, **kwargs) for item in iterable]

    processes = processes or CPU_CNT
    lock = mp.Lock()
    with mp.Pool(processes=processes, initializer=_mp_init_lock, initargs=(lock,)) as pool:  # parallel execution
        result = pool.map(_mp_map_wrapper, [(func, (item,) + tuple(posargs), kwargs) for item in iterable], chunksize)
    task_lock = nullcontext()
    return result


task_lock = nullcontext()


def TaskLock():
    """Function that returns a lock for possibly concurrent tasks.

    Returns:
        Union[contextlib.nullcontext, multiprocessing.synchronize.Lock]: a lock for possibly concurrent tasks

    """
    return task_lock


__all__ = ['map_tasks', 'TaskLock']
