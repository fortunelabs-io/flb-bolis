"""The Bolis host package.

Holds the CLI, the flasher, the orchestrator, the run record writer, and the
report builder (thinkbook section 6).
"""

from importlib.metadata import version

__version__ = version("bolis")


class BolisError(Exception):
    """The base class of every exception that the Bolis host package raises."""
