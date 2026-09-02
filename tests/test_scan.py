"""Filesystem discovery: candidate indexing and hardlink de-duplication."""

import argparse
import os
import stat as stat_mod

import pytest

import torram_ng.cli as cli
from torram_ng.cli import get_possible_files, remove_hard_links


@pytest.fixture(autouse=True)
def _args(monkeypatch):
    """The module reads a global ``args``; give it a quiet default."""
    monkeypatch.setattr(cli, "args", argparse.Namespace(verbose=0, minsize=0))


def _touch(path, size):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "wb") as fh:
        fh.write(b"\0" * size)


def test_finds_files_matching_a_requested_size(tmp_path):
    _touch(tmp_path / "a" / "match.bin", 500)
    _touch(tmp_path / "b" / "other.bin", 999)

    found = get_possible_files(str(tmp_path), [500])

    assert list(found) == [500]
    assert [os.path.basename(p) for p in found[500]] == ["match.bin"]


def test_groups_multiple_candidates_under_one_size(tmp_path):
    _touch(tmp_path / "one" / "copy.bin", 500)
    _touch(tmp_path / "two" / "copy.bin", 500)

    found = get_possible_files(str(tmp_path), [500])

    assert len(found[500]) == 2


def test_recurses_into_subdirectories(tmp_path):
    _touch(tmp_path / "x" / "y" / "z" / "deep.bin", 42)

    found = get_possible_files(str(tmp_path), [42])

    assert len(found[42]) == 1


def test_ignores_sizes_not_requested(tmp_path):
    _touch(tmp_path / "nope.bin", 123)

    assert get_possible_files(str(tmp_path), [500]) == {}


def test_hardlinks_to_the_same_inode_collapse_to_one(tmp_path):
    original = tmp_path / "original.bin"
    _touch(original, 100)
    link = tmp_path / "hardlink.bin"
    os.link(str(original), str(link))

    kept = list(remove_hard_links([str(original), str(link)]))

    assert len(kept) == 1


def test_distinct_files_are_all_kept(tmp_path):
    a, b = tmp_path / "a.bin", tmp_path / "b.bin"
    _touch(a, 100)
    _touch(b, 100)

    kept = set(remove_hard_links([str(a), str(b)]))

    assert kept == {str(a), str(b)}


@pytest.mark.xfail(
    strict=True,
    reason="hardlink dedup keys on st_ino without st_dev -- issue #6",
)
def test_same_inode_on_different_devices_are_both_kept(tmp_path, monkeypatch):
    """Inode numbers are only unique within a filesystem.

    Two unrelated files on two different drives routinely share an inode number.
    Keying the de-duplication dict on ``st_ino`` alone silently discards one of
    them, which breaks the scan-several-disks use case this tool exists for.
    """
    a, b = tmp_path / "disk1.bin", tmp_path / "disk2.bin"
    _touch(a, 100)
    _touch(b, 100)

    shared_inode = 4242
    devices = {str(a): 2049, str(b): 2050}

    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        if str(path) in devices:
            fields = list(st)
            fields[stat_mod.ST_INO] = shared_inode
            fields[stat_mod.ST_DEV] = devices[str(path)]
            return os.stat_result(fields)
        return st

    monkeypatch.setattr(os, "stat", fake_stat)

    kept = set(remove_hard_links([str(a), str(b)]))

    assert kept == {str(a), str(b)}
