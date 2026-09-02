"""End-to-end tests through the real command line entry point.

Every subprocess call carries a timeout: the tool has a known input loop that can
spin forever (issue #10), and a hanging test suite is worse than a failing one.
"""

import filecmp
import os
import subprocess
import sys

import pytest

import fixtures
from torram_ng import __version__

TIMEOUT = 60


def run(*argv):
    return subprocess.run(
        [sys.executable, "-m", "torram_ng.cli", *argv],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def complete_source(tmp_path, torrent_a):
    """A pristine, byte-for-byte complete copy of every file in torrent A."""
    torrent, _stream, contents = torrent_a
    (tmp_path / "test.torrent").write_bytes(torrent)
    fixtures.write_tree(tmp_path / "src", contents)
    return tmp_path


def test_version():
    result = run("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_help_lists_the_positional_arguments():
    result = run("--help")
    assert result.returncode == 0
    assert "torrentFile" in result.stdout
    assert "root" in result.stdout


def test_missing_arguments_exits_nonzero():
    result = run()
    assert result.returncode != 0


def _recover(base):
    return run(
        str(base / "test.torrent"),
        str(base / "src"),
        "-o",
        str(base / "out"),
        "-ss",
        "--minsize",
        "0",
    )


def test_recovery_from_complete_source_succeeds(complete_source):
    result = _recover(complete_source)
    assert result.returncode == 0, result.stderr


def test_recovered_files_are_byte_identical(complete_source):
    _recover(complete_source)
    out = complete_source / "out" / "gauntlet"

    for relative in ("a.bin", os.path.join("subdir", "b.bin"), "unicode-café-日本語.bin"):
        produced = out / relative
        assert produced.exists(), relative
        assert filecmp.cmp(str(complete_source / "src" / relative), str(produced), shallow=False), relative


def test_unicode_path_round_trips_through_recovery(complete_source):
    _recover(complete_source)
    assert (complete_source / "out" / "gauntlet" / "unicode-café-日本語.bin").exists()


@pytest.mark.xfail(
    strict=True,
    reason="under -ss a file with no attributable pieces is auto-skipped -- issue #3",
)
def test_sub_piece_file_is_recovered(complete_source):
    """A file with no attributable pieces is dropped in automated mode.

    Because no piece maps to tiny.txt, ``suggest_method`` returns 'S' and the
    file is skipped. Interactively the user can still override that by choosing
    a candidate number, so this is a bad default rather than an unavoidable
    loss -- but under -s/-ss there is no prompt and the file is dropped with the
    run still exiting 0.
    """
    _recover(complete_source)
    assert (complete_source / "out" / "gauntlet" / "tiny.txt").exists()


@pytest.mark.xfail(
    strict=True,
    reason="pieces spanning file boundaries never verify -- issue #3",
)
def test_complete_source_verifies_every_piece(complete_source):
    """The clearest statement of the core defect.

    The source is a perfect copy, so every piece should verify. Instead a.bin
    reports '3 of 4' and subdir/b.bin reports '1 of 2', because the pieces that
    straddle a file boundary are read from one file only and hash a short buffer.
    """
    result = _recover(complete_source)
    assert "[3 of 4]" not in result.stdout
    assert "[1 of 2]" not in result.stdout


@pytest.mark.xfail(
    strict=True,
    reason="zero-length files are excluded by the `> minsize` test -- issue #11",
)
def test_zero_length_file_is_created(complete_source):
    _recover(complete_source)
    assert (complete_source / "out" / "gauntlet" / "empty.dat").exists()
