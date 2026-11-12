"""The Bolis host package.

Holds the CLI, the flasher, the control line codec, the control line
transport, and the sweep plan.
"""

from importlib.metadata import version

__version__ = version("bolis")


class BolisError(Exception):
    """The base class of every exception that the Bolis host package raises."""
