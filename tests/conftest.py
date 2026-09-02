import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import fixtures

DATA = pathlib.Path(__file__).parent / "data"


@pytest.fixture
def torrent_a():
    """Multi-file gauntlet: unaligned sizes, zero-length file, sub-piece file,
    nested path, unicode path, partial final piece, three-file spanning piece."""
    torrent, stream, contents = fixtures.torrent_a()
    return torrent, stream, contents


@pytest.fixture
def torrent_b():
    """Single file, an exact multiple of the piece length: no partial final piece."""
    torrent, stream, contents = fixtures.torrent_b()
    return torrent, stream, contents


@pytest.fixture
def debian_torrent():
    return (DATA / "debian-13.6.0-amd64-netinst.iso.torrent").read_bytes()


@pytest.fixture
def bbb_torrent():
    return (DATA / "BigBuckBunny_124_archive.torrent").read_bytes()
