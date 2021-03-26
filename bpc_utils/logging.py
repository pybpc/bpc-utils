"""Logging system for BPC."""

import logging
import time

from .typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import LogRecord


class BPCHandler(logging.StreamHandler):
    """Handler used to convey BPC logging records."""

    def format(self, record: 'LogRecord') -> str:
        """Format the specified record based on logging level.

        The record will be formatted based on its logging level
        in the following flavour:

        +--------------+-----------------------------------------------+
        | ``DEBUG``    | ``[%(levelname)s] %(asctime)s - %(message)s`` |
        +--------------+-----------------------------------------------+
        | ``INFO``     | ``%(message)s``                               |
        +--------------+-----------------------------------------------+
        | ``WARNING``  | ``Warning: %(message)s``                      |
        +--------------+-----------------------------------------------+
        | ``ERROR``    | ``Error: %(message)s``                        |
        +--------------+-----------------------------------------------+
        | ``CRITICAL`` | ``Error: %(message)s``                        |
        +--------------+-----------------------------------------------+

        """
        level = record.levelname
        if level == 'DEBUG':
            template = '[%(levelname)s] %(asctime)s - %(message)s'
        elif level == 'INFO':
            template = '%(message)s'
        elif level == 'WARNING':
            template = 'Warning: %(message)s'
        elif level == 'ERROR':
            template = 'Error: %(message)s'
        elif level == 'CRITICAL':
            template = 'Error: %(message)s'
        else:
            template = '%(levelname)s: %(message)s'
        return template % {
            'levelname': level,
            'asctime': time.strftime(r'%m/%d/%Y %I:%M:%S %p',
                                     time.localtime(record.created)),
            'message': record.getMessage(),
        }


def getLogger(name: str) -> 'logging.Logger':
    """Create a BPC logger.

    Args:
        name: Name of the created logger.

    """
    logger = logging.getLogger(name)
    logger.addHandler(BPCHandler())
    return logger


__all__ = ['getLogger']
