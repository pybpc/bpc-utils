.. bpc-utils documentation master file, created by
   sphinx-quickstart on Thu Feb 13 22:20:47 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Python Backport Compiler Utilities
==================================

Utility library for the Python |bpc|_ backport compiler.

.. |bpc| replace:: ``bpc``
.. _bpc: https://github.com/pybpc/bpc

Currently, the three individual tools (|f2format|_, |poseur|_,
|walrus|_) depend on this repo. The |bpc|_ compiler is a
work in progress.

.. |f2format| replace:: ``f2format``
.. _f2format: https://github.com/pybpc/f2format
.. |poseur| replace:: ``poseur``
.. _poseur: https://github.com/pybpc/poseur
.. |walrus| replace:: ``walrus``
.. _walrus: https://github.com/pybpc/walrus

Module contents
---------------

.. automodule:: bpc_utils
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: TaskLock

.. function:: bpc_utils.TaskLock

   A lock for possibly concurrent tasks.

   :rtype: Union[contextlib.nullcontext, multiprocessing.Lock]

Internal utilities
------------------

.. autoclass:: bpc_utils.MakeTextIO
   :members:
   :undoc-members:
   :show-inheritance:

   .. attribute:: obj
      :type: Union[str, TextIO]

      The object to manage in the context.

   .. attribute:: sio
      :type: StringIO

      The I/O object to manage in the context if only :
      attr:`self.obj <MakeTextIO.obj>` is ``str``.

   .. attribute:: pos
      :type: int

      The original offset of :attr:`self.obj <MakeTextIO.obj>`,
      if only :attr:`self.obj <MakeTextIO.obj>` is ``TextIO``.

.. function:: bpc_utils.expand_glob_iter(pathname)

   Wrapper function to perform glob expansion.

   :param str pathname: pathname pattern
   :returns: an iterator which yields the paths matching a pathname pattern
   :rtype: Iterator[str]

.. autofunction:: bpc_utils._mp_map_wrapper

.. data:: mp
   :type: Optional[ModuleType]
   :value: <module 'multiprocessing'>

   An alias of the Python builtin :mod:`multiprocessing` module if available.

.. data:: CPU_CNT
   :type: int

   Number of CPUs for multiprocessing support.

.. data:: parallel_available
   :type: bool

   Whether parallel execution is available.

.. autodata:: bpc_utils._boolean_state_lookup
.. autodata:: bpc_utils._linesep_lookup

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
