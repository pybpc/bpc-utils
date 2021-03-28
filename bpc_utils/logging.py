"""Logging system for BPC."""

import logging

from .misc import current_time_with_tzinfo
from .typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .typing import Dict


class BPCLogHandler(logging.StreamHandler):
    """Handler used to format BPC logging records."""

    format_templates = {
        'DEBUG': '[%(levelname)s] %(asctime)s %(message)s',
        'INFO': '%(message)s',
        'WARNING': 'Warning: %(message)s',
        'ERROR': 'Error: %(message)s',
        'CRITICAL': 'Error: %(message)s',
    }  # type: Dict[str, str]

    # An extension of the standard `%(asctime)s` to include local time zone.
    time_format = '%Y-%m-%d %H:%M:%S.%f%z'

    def __init__(self) -> None:
        """Initialize BPCLogHandler."""
        super().__init__()

    # Let `BPCLogHandler` instances equal to each other.
    # This is to prevent `logger.addHandler(BPCLogHandler())` from adding multiple handlers when called multiple times.
    def __eq__(self, other: object) -> bool:
        return type(self) is type(other)

    def __hash__(self) -> int:
        return hash(())

    def format(self, record: 'logging.LogRecord') -> str:
        """Format the specified record based on log level.

        The record will be formatted based on its log level
        in the following flavour:

        +--------------+-----------------------------------------------+
        | ``DEBUG``    | ``[%(levelname)s] %(asctime)s %(message)s``   |
        +--------------+-----------------------------------------------+
        | ``INFO``     | ``%(message)s``                               |
        +--------------+-----------------------------------------------+
        | ``WARNING``  | ``Warning: %(message)s``                      |
        +--------------+-----------------------------------------------+
        | ``ERROR``    | ``Error: %(message)s``                        |
        +--------------+-----------------------------------------------+
        | ``CRITICAL`` | ``Error: %(message)s``                        |
        +--------------+-----------------------------------------------+

        Args:
            record: the log record

        Returns:
            the formatted log string

        """
        level = record.levelname.upper()
        # Only the 5 predefined log levels are supported
        return self.format_templates[level] % {
            'levelname': level,
            'asctime': current_time_with_tzinfo().strftime(self.time_format),
            'message': record.getMessage(),
        }


def getLogger(name: str, level: int = logging.INFO) -> 'logging.Logger':
    """Create a BPC logger.

    Args:
        name: name for the logger
        level: log level for the logger

    Returns:
        the created logger

    """
    logger = logging.getLogger(name)
    # We cannot create a single global `BPCLogHandler` instance on start
    # because pytest cannot capture output from that.
    # See: https://stackoverflow.com/questions/38594296/how-to-use-logging-pytest-fixture-and-capsys
    logger.addHandler(BPCLogHandler())
    logger.setLevel(level)
    return logger


__all__ = ['getLogger']
