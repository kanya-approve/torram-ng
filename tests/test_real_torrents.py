"""Exercise torram's offset map against real torrents.

Metadata only, no content download. The point is not to assert facts about the
committed files -- it is to run the real mapping code over real-world shapes
that the generated fixtures cannot fully imitate: 3020 pieces in one case, and
twelve files with nine of them smaller than a piece in the other.

See ``tests/data/README.md`` for provenance.
"""

import bencode

from torram_ng.cli import get_chunk


def _sizes(info):
    return [f["length"] for f in info["files"]]


def test_every_file_start_maps_back_to_its_own_index(bbb_torrent):
    """Walking the cumulative offsets must land on each file in turn."""
    info = bencode.bdecode(bbb_torrent)["info"]
    sizes = _sizes(info)

    offset = 0
    for index, length in enumerate(sizes):
        assert get_chunk(sizes, offset) == (index, 0), index
        offset += length


def test_every_piece_start_maps_into_a_real_file(bbb_torrent):
    """No piece boundary may fall outside the file list."""
    info = bencode.bdecode(bbb_torrent)["info"]
    sizes = _sizes(info)
    piece_length = info["piece length"]
    total = sum(sizes)

    for piece in range(len(info["pieces"]) // 20):
        index, offset = get_chunk(sizes, piece * piece_length)
        assert 0 <= index < len(sizes), piece
        assert 0 <= offset < sizes[index], piece

    # One past the final byte is the only offset allowed to run off the end.
    assert get_chunk(sizes, total)[0] == len(sizes)


def test_offsets_within_a_file_are_relative_to_that_file(bbb_torrent):
    info = bencode.bdecode(bbb_torrent)["info"]
    sizes = _sizes(info)

    start = sum(sizes[:8])  # the large video file
    index, offset = get_chunk(sizes, start + 1234)
    assert (index, offset) == (8, 1234)


def test_single_file_torrent_maps_every_piece_to_index_zero(debian_torrent):
    info = bencode.bdecode(debian_torrent)["info"]
    sizes = [info["length"]]
    piece_length = info["piece length"]
    pieces = len(info["pieces"]) // 20

    assert pieces == 3020
    for piece in range(pieces):
        index, offset = get_chunk(sizes, piece * piece_length)
        assert index == 0, piece
        assert offset == piece * piece_length
