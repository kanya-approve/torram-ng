"""``get_file_sizes`` -- which file sizes the scanner will look for on disk."""

import argparse

import bencode
import pytest

import fixtures
import torram_ng.cli as cli
from torram_ng.cli import get_file_sizes


@pytest.fixture
def minsize(monkeypatch):
    def _set(value):
        monkeypatch.setattr(cli, "args", argparse.Namespace(verbose=0, minsize=value))

    return _set


def _info(torrent):
    return bencode.bdecode(torrent)["info"]


def test_returns_every_file_when_no_minimum_is_set(minsize, torrent_a):
    minsize(0)
    torrent, _, _ = torrent_a

    assert sorted(get_file_sizes(_info(torrent))) == [10, 33000, 70000, 100000]


def test_zero_length_files_are_excluded(minsize, torrent_a):
    """The filter is ``length > minsize``, so a zero-length file never survives
    even with a minimum of zero."""
    minsize(0)
    torrent, _, _ = torrent_a

    assert 0 not in get_file_sizes(_info(torrent))


def test_filters_out_files_at_or_below_the_minimum(minsize, torrent_a):
    minsize(50000)
    torrent, _, _ = torrent_a

    assert sorted(get_file_sizes(_info(torrent))) == [70000, 100000]


def test_single_file_torrents_ignore_the_minimum(minsize, torrent_b):
    """The single-file branch returns the length unconditionally while the
    multi-file branch filters -- an inconsistency between the two paths."""
    minsize(fixtures.TORRENT_B_LENGTH * 10)
    torrent, _, _ = torrent_b

    assert get_file_sizes(_info(torrent)) == [fixtures.TORRENT_B_LENGTH]
