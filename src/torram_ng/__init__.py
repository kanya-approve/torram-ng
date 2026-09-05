"""torram-ng: recover torrent data from fully and partially downloaded files."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("torram-ng")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0+unknown"

__all__ = ["__version__"]
