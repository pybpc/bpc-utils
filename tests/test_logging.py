import datetime
import logging
import os
import re
import shutil
import subprocess  # nosec
import sys
import textwrap

import pytest

from bpc_utils import getLogger
from bpc_utils.logging import BPCLogHandler
from bpc_utils.misc import current_time_with_tzinfo
from bpc_utils.typing import TYPE_CHECKING

from .testutils import write_text_file

if TYPE_CHECKING:
    from pathlib import Path  # isort: split
    from bpc_utils.typing import Tuple  # isort: split
    from .testutils import CaptureFixture, MonkeyPatch


def test_BPCLogHandler() -> None:
    class BPCLogHandlerSubclass(BPCLogHandler):
        pass

    handler1 = BPCLogHandler()
    handler2 = BPCLogHandlerSubclass()
    handler3 = BPCLogHandler()
    assert handler1 is not handler3
    assert handler1 == handler3
    assert handler1 is not handler2
    assert handler1 != handler2
    assert handler3 != 1
    assert 1 != handler3  # pylint: disable=misplaced-comparison-constant


def test_getLogger_multiple() -> None:
    logger1 = getLogger('bpc_utils_test_logger1', level=logging.DEBUG)
    logger2 = getLogger('bpc_utils_test_logger2', level=logging.DEBUG)
    logger3 = getLogger('bpc_utils_test_logger1')
    assert logger1 is logger3
    assert logger1 is not logger2
    assert len(logger1.handlers) == 1
    assert len(logger2.handlers) == 1
    assert logger1.level == logging.INFO
    assert logger2.level == logging.DEBUG


def test_logging_level_and_format(capsys: 'CaptureFixture[str]') -> None:
    debug_message = 'debug output'
    info_message = 'some information'
    warning_message = 'no files supplied'
    error_message_args = ('error converting file %r', 'script.py')  # type: Tuple[str, str]
    critical_message = 'invalid option'

    # test default level is INFO, and INFO log format
    logger_name = 'bpc_utils_test_logging_level'
    logger = getLogger(logger_name)
    logger.info(info_message)
    logger.debug(debug_message)
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.splitlines() == [info_message]

    # test DEBUG log format
    logger_name = 'bpc_utils_test_logging_format'
    logger = getLogger(logger_name, level=logging.DEBUG)
    logger.debug(debug_message)
    captured = capsys.readouterr()
    assert not captured.out
    log_messages = captured.err.splitlines()
    assert len(log_messages) == 1
    m = re.fullmatch(r'\[DEBUG\] (.*?) ' + re.escape(debug_message), log_messages[0])
    assert m
    log_time = datetime.datetime.strptime(m.group(1), BPCLogHandler.time_format)
    current_time = current_time_with_tzinfo()
    assert current_time >= log_time
    assert current_time - log_time < datetime.timedelta(minutes=1)

    # test WARNING log format
    logger.warning(warning_message)
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.splitlines() == ['Warning: ' + warning_message]

    # test ERROR log format
    logger.error(*error_message_args)
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.splitlines() == ['Error: ' + error_message_args[0] % error_message_args[1]]

    # test CRITICAL log format
    logger.critical(critical_message)
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err.splitlines() == ['Error: ' + critical_message]


num_tasks = 10
logging_mp_code_style1 = textwrap.dedent("""\
    import logging

    from bpc_utils import TaskLock, getLogger, map_tasks

    logger = getLogger('test_logging_multiprocessing')


    def task(x):
        logger.setLevel(logging.DEBUG)  # this is needed when multiprocessing start method is not 'fork'
        with TaskLock():
            logger.debug(x)


    if __name__ == '__main__':
        logger.setLevel(logging.DEBUG)
        map_tasks(task, range({num_tasks}))
""").format(num_tasks=num_tasks)
logging_mp_code_style2 = textwrap.dedent("""\
    import logging

    from bpc_utils import TaskLock, getLogger, map_tasks


    def task(x):
        logger = getLogger('test_logging_multiprocessing', level=logging.DEBUG)
        with TaskLock():
            logger.debug(x)


    if __name__ == '__main__':
        map_tasks(task, range({num_tasks}))
""").format(num_tasks=num_tasks)


@pytest.mark.parametrize(
    'code',
    [
        logging_mp_code_style1,
        logging_mp_code_style2,
    ]
)
def test_logging_multiprocessing(code: str, tmp_path: 'Path', monkeypatch: 'MonkeyPatch',
                                 capfd: 'CaptureFixture[str]') -> None:
    monkeypatch.chdir(tmp_path)
    shutil.copytree(os.path.dirname(sys.modules['bpc_utils'].__file__), 'bpc_utils')
    test_filename = 'test_logging_multiprocessing.py'
    write_text_file(test_filename, code)
    subprocess.check_call([sys.executable, '-u', test_filename])  # nosec
    captured = capfd.readouterr()
    assert not captured.out
    assert sorted(int(line.split()[-1]) for line in captured.err.splitlines()) == list(range(num_tasks))
