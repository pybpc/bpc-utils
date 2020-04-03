bpc\_utils module
=================

Module contents
---------------

.. automodule:: bpc_utils
   :members:
   :undoc-members:
   :show-inheritance:

Internal utilities
------------------

.. data:: mp
   :type: Optional[module]
   :value: <module 'multiprocessing'>

   An alias of the Python builtin ``multiprocessing`` module if available.

.. data:: CPU_CNT
   :type: int

   Number of CPUs for multiprocessing support.

.. data:: parallel_available
   :type: bool

   Whether parallel execution is available.

.. autoclass:: bpc_utils.MakeTextIO
   :members:
   :undoc-members:
   :show-inheritance:

   .. attribute:: obj
      :type: Union[str, TextIO]

      The object to manage in the context.

   .. attribute:: sio
      :type: StringIO

      The I/O object to manage in the context
      if only :attr:`self.obj <MakeTextIO.obj>` is :obj:`str`.

   .. attribute:: pos
      :type: int

      The original offset of :attr:`self.obj <MakeTextIO.obj>`,
      if only :attr:`self.obj <MakeTextIO.obj>` is a seekable :obj:`TextIO`.

.. autofunction:: bpc_utils.expand_glob_iter
.. autofunction:: bpc_utils._mp_map_wrapper

.. autodata:: bpc_utils._boolean_state_lookup
.. autodata:: bpc_utils._linesep_lookup
