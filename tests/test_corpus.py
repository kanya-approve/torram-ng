"""Tests driven by libtorrent's adversarial torrent corpus.

See ``tests/data/libtorrent/README.md``. These torrents carry no content, so
they exercise parsing, path handling and the offset map -- not piece hashing.
"""

import os
import pathlib

import bencode
import pytest

from torram_ng.cli import get_chunk

CORPUS = pathlib.Path(__file__).parent / "data" / "libtorrent"

# Torrents that decode cleanly but whose declared paths escape the output
# directory. Enumerated explicitly so a change in the vendored corpus is noticed.
# backslash_path.torrent is deliberately absent: on POSIX a backslash is an
# ordinary filename character, so it resolves inside the output directory. It is
# an escape only on Windows, which is out of scope until that platform is tested.
ESCAPING = [
    "absolute_filename.torrent",
    "hidden_parent_path.torrent",
    "invalid_directory_name.torrent",
    "invalid_filename2.torrent",
    "parent_path.torrent",
    "slash_path.torrent",
    "slash_path2.torrent",
    "slash_path3.torrent",
    "symlink_filtered_path.torrent",
]

# Torrents that decode but crash the file/size handling with an unhandled
# KeyError or TypeError rather than a diagnosable error. invalid_file_size
# declares a length of [45] -- a list -- so it only breaks once the size is used.
CRASHING = [
    "invalid_file_size.torrent",
    "invalid_path_list.torrent",
    "invalid_symlink.torrent",
    "missing_path_list.torrent",
    "pad_file_no_path.torrent",
    "symlink_zero_size.torrent",
]


def _decode(name):
    return bencode.bdecode((CORPUS / name).read_bytes())["info"]


def _destinations(info, output_root):
    """Reproduce how the tool builds an output path for each file."""
    base = info["name"]
    if "files" not in info:
        return [os.path.join(output_root, base)]
    return [os.path.join(output_root, base, os.path.join(*f["path"])) for f in info["files"]]


def _parsable():
    names = []
    for path in sorted(CORPUS.glob("*.torrent")):
        try:
            info = bencode.bdecode(path.read_bytes())["info"]
            [f["length"] for f in info["files"]] if "files" in info else info["length"]
        except Exception:
            continue
        names.append(path.name)
    return names


PARSABLE = _parsable()


def test_the_corpus_is_present():
    assert len(list(CORPUS.glob("*.torrent"))) == 100


@pytest.mark.parametrize("name", ESCAPING)
@pytest.mark.xfail(
    strict=True,
    reason="torrent paths are joined without sanitization -- issue #7",
)
def test_declared_paths_cannot_escape_the_output_directory(name, tmp_path):
    """A .torrent is untrusted input. No declared path may resolve outside the
    directory the user chose.

    ``os.path.join`` discards everything before an absolute component, so a path
    of ``/foobar`` yields ``/foobar`` regardless of the output directory, and
    ``../../bar`` climbs out of it.
    """
    root = str(tmp_path)
    for dest in _destinations(_decode(name), root):
        resolved = os.path.realpath(dest)
        assert resolved.startswith(os.path.realpath(root) + os.sep), dest


@pytest.mark.parametrize("name", CRASHING)
@pytest.mark.xfail(
    strict=True,
    reason="malformed torrents raise KeyError/TypeError instead of a diagnosable error -- issue #9",
)
def test_malformed_torrents_do_not_crash_file_handling(name):
    """Reading a hostile torrent should fail with something the caller can
    report, not an unhandled KeyError or TypeError from deep inside."""
    info = _decode(name)
    try:
        if "files" in info:
            [os.path.join(*f["path"]) for f in info["files"]]
            sizes = [f["length"] for f in info["files"]]
        else:
            sizes = [info["length"]]
        get_chunk(sizes, 0)
        sum(sizes)
    except (KeyError, TypeError) as exc:
        pytest.fail(f"unhandled {type(exc).__name__}: {exc}")


@pytest.mark.parametrize("name", PARSABLE)
def test_offset_map_is_self_consistent_across_the_corpus(name):
    """For every torrent the tool can read, walking the cumulative file offsets
    must land on each file in turn, and no piece boundary may fall outside the
    file list."""
    info = _decode(name)
    sizes = [f["length"] for f in info["files"]] if "files" in info else [info["length"]]
    if not all(isinstance(s, int) and s >= 0 for s in sizes):
        pytest.skip("malformed file size; a separate parser-validation concern")

    offset = 0
    for index, length in enumerate(sizes):
        if length == 0:
            continue
        assert get_chunk(sizes, offset) == (index, 0), (name, index)
        offset += length

    assert get_chunk(sizes, sum(sizes))[0] == len(sizes)
