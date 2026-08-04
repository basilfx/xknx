"""
Command line interface for interacting with devices on a KNX bus.

**Experimental.** This subpackage is a thin CLI wrapper around the xknx
library (:mod:`xknx.tools`, :mod:`xknx.management`, :mod:`xknx.io`) and its
command surface may still change in a future release.
"""

from .main import cli

__all__ = ["cli"]
