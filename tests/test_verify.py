"""Piece verification against real generated content."""

import hashlib
import os

import pytest

import fixtures
from torram_ng.cli import check_file_chunk, get_chunk


def _piece_digest(stream, index, piece_length):
    return hashlib.sha1(stream[index * piece_length : (index + 1) * piece_length]).digest()


def test_piece_fully_inside_one_file_verifies(tmp_path, torrent_a):
    _, stream, contents = torrent_a
    fixtures.write_tree(tmp_path, contents)

    # Piece 0 lies entirely within a.bin (100000 bytes, piece length 32768).
    digest = _piece_digest(stream, 0, fixtures.TORRENT_A_PIECE_LENGTH)
    path = os.path.join(str(tmp_path), "a.bin")

    assert check_file_chunk(digest, 0, fixtures.TORRENT_A_PIECE_LENGTH, path) is True


def test_wrong_data_does_not_verify(tmp_path, torrent_a):
    _, stream, contents = torrent_a
    fixtures.write_tree(tmp_path, contents)

    digest = _piece_digest(stream, 0, fixtures.TORRENT_A_PIECE_LENGTH)
    path = os.path.join(str(tmp_path), "a.bin")

    assert check_file_chunk(digest, fixtures.TORRENT_A_PIECE_LENGTH, fixtures.TORRENT_A_PIECE_LENGTH, path) is False


def test_single_file_torrent_all_pieces_verify(tmp_path, torrent_b):
    _, stream, contents = torrent_b
    fixtures.write_tree(tmp_path, contents)
    path = os.path.join(str(tmp_path), "aligned.bin")

    piece_length = fixtures.TORRENT_B_PIECE_LENGTH
    for index in range(len(stream) // piece_length):
        digest = _piece_digest(stream, index, piece_length)
        assert check_file_chunk(digest, index * piece_length, piece_length, path) is True, index


@pytest.mark.xfail(
    strict=True,
    reason="a piece spanning file boundaries is read from one file only -- issue #3",
)
def test_spanning_piece_verifies(tmp_path, torrent_a):
    """Piece 3 spans a.bin, tiny.txt and subdir/b.bin.

    ``check_file_chunk`` seeks into a.bin and asks for a full piece, but only
    1,696 bytes remain there, so it hashes a truncated buffer and can never
    match. Every piece straddling a file boundary fails this way.
    """
    _, stream, contents = torrent_a
    fixtures.write_tree(tmp_path, contents)

    piece_length = fixtures.TORRENT_A_PIECE_LENGTH
    digest = _piece_digest(stream, 3, piece_length)
    sizes = [length for _, length in fixtures.TORRENT_A_FILES]
    _, offset = get_chunk(sizes, 3 * piece_length)

    assert check_file_chunk(digest, offset, piece_length, os.path.join(str(tmp_path), "a.bin")) is True


def test_final_partial_piece_verifies_when_sizes_match(tmp_path, torrent_a):
    """The last piece of torrent A is 6,402 bytes, not a full 32,768.

    This happens to work because the candidate is exactly the size the torrent
    declares, so the short read at EOF returns precisely the right bytes. It is
    accidental rather than intended -- see issue #12.
    """
    _, stream, contents = torrent_a
    fixtures.write_tree(tmp_path, contents)

    piece_length = fixtures.TORRENT_A_PIECE_LENGTH
    last = len(stream) // piece_length
    assert len(stream) % piece_length == 6402

    digest = _piece_digest(stream, last, piece_length)
    sizes = [length for _, length in fixtures.TORRENT_A_FILES]
    idx, offset = get_chunk(sizes, last * piece_length)

    path = os.path.join(str(tmp_path), "unicode-café-日本語.bin")
    assert idx == 4
    assert check_file_chunk(digest, offset, piece_length, path) is True
