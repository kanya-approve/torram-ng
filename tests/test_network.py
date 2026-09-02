"""Verification against real torrents and their real content, fetched over HTTPS.

No BitTorrent client is involved. Both sources publish the same bytes over plain
HTTPS, so CI can fetch them directly:

* **Debian** serves the netinst ISO with ``Accept-Ranges: bytes``, so a few MiB
  of range requests verify real pieces without the 791 MB download.
* **archive.org** generates a torrent per item and serves every file at a
  predictable URL. The torrent is fetched at test time alongside the content, so
  the two can never drift apart if the item is re-derived.

The value here is checking our piece arithmetic against SHA-1 hashes produced by
somebody else's implementation, on layouts we did not choose.

Marked ``network`` and deselected by default; run with ``pytest -m network``.
"""

import hashlib
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import bencode
import pytest

pytestmark = pytest.mark.network

DATA = pathlib.Path(__file__).parent / "data"
TIMEOUT = 120

DEBIAN_TORRENT = DATA / "debian-13.6.0-amd64-netinst.iso.torrent"
DEBIAN_URLS = [
    "https://cdimage.debian.org/cdimage/release/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso",
    "https://cdimage.debian.org/cdimage/archive/13.6.0/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso",
]

# Project Gutenberg's "Alice's Adventures in Wonderland" as held by archive.org.
# Public domain. 63 files totalling 3.8 MB, of which 62 are smaller than the
# 512 KiB piece length -- so almost every piece spans many files.
ARCHIVE_ITEM = "alicesadventures19033gut"


def _fetch(url, byte_range=None):
    request = urllib.request.Request(url)
    if byte_range:
        request.add_header("Range", "bytes={}-{}".format(*byte_range))
    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
    raise AssertionError(f"could not fetch {url}: {last}")


def _fetch_first_available(urls, byte_range=None):
    errors = []
    for url in urls:
        try:
            return _fetch(url, byte_range)
        except AssertionError as exc:
            errors.append(str(exc))
    pytest.skip("no mirror reachable: {}".format("; ".join(errors)))


def _piece_digests(info):
    blob = info["pieces"]
    return [blob[i : i + 20] for i in range(0, len(blob), 20)]


def test_debian_iso_pieces_verify_against_real_bytes():
    """Range-fetch the head of the ISO and check it against Debian's own hashes."""
    info = bencode.bdecode(DEBIAN_TORRENT.read_bytes())["info"]
    piece_length = info["piece length"]
    wanted = 16  # 16 x 256 KiB = 4 MiB

    data = _fetch_first_available(DEBIAN_URLS, (0, wanted * piece_length - 1))
    assert len(data) == wanted * piece_length

    expected = _piece_digests(info)
    for index in range(wanted):
        chunk = data[index * piece_length : (index + 1) * piece_length]
        assert hashlib.sha1(chunk).digest() == expected[index], index


def test_debian_iso_length_matches_the_torrent():
    request = urllib.request.Request(DEBIAN_URLS[0], method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            length = int(response.headers["Content-Length"])
    except (urllib.error.URLError, TimeoutError) as exc:
        pytest.skip(f"mirror unreachable: {exc}")

    info = bencode.bdecode(DEBIAN_TORRENT.read_bytes())["info"]
    assert length == info["length"]


@pytest.fixture(scope="module")
def archive_item(tmp_path_factory):
    """Fetch the torrent and every file it lists, in parallel."""
    torrent = _fetch(f"https://archive.org/download/{ARCHIVE_ITEM}/{ARCHIVE_ITEM}_archive.torrent")
    info = bencode.bdecode(torrent)["info"]
    root = tmp_path_factory.mktemp(ARCHIVE_ITEM)

    def download(entry):
        relative = "/".join(entry["path"])
        url = f"https://archive.org/download/{ARCHIVE_ITEM}/{urllib.parse.quote(relative)}"
        target = root.joinpath(*entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_fetch(url))

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(download, info["files"]))

    return info, root


def test_archive_item_files_match_their_declared_sizes(archive_item):
    info, root = archive_item
    for entry in info["files"]:
        target = root.joinpath(*entry["path"])
        assert target.stat().st_size == entry["length"], "/".join(entry["path"])


def test_archive_item_is_mostly_sub_piece_files(archive_item):
    """Guards the property that makes this fixture worth downloading: if the item
    is ever re-derived into a few large files, it stops exercising spanning."""
    info, _ = archive_item
    piece_length = info["piece length"]
    small = [f for f in info["files"] if f["length"] < piece_length]
    assert len(small) >= len(info["files"]) - 2


def test_archive_item_every_piece_verifies_across_file_boundaries(archive_item):
    """Assemble the global stream from 63 separate files and check every piece.

    Nearly every piece here spans several files, so this is the cross-boundary
    case verified against hashes archive.org computed independently.
    """
    info, root = archive_item
    piece_length = info["piece length"]
    expected = _piece_digests(info)

    digest = hashlib.sha1()
    buffered = 0
    index = 0
    for entry in info["files"]:
        data = root.joinpath(*entry["path"]).read_bytes()
        position = 0
        while position < len(data):
            take = min(piece_length - buffered, len(data) - position)
            digest.update(data[position : position + take])
            buffered += take
            position += take
            if buffered == piece_length:
                assert digest.digest() == expected[index], index
                digest, buffered = hashlib.sha1(), 0
                index += 1
    if buffered:
        assert digest.digest() == expected[index], "final partial piece"
        index += 1

    assert index == len(expected)


@pytest.mark.xfail(
    strict=True,
    reason="check_file_chunk reads a single file, so spanning pieces fail -- issue #3",
)
def test_check_file_chunk_verifies_a_spanning_piece_of_a_real_torrent(archive_item):
    """The same defect the generated fixtures show, reproduced on a real torrent.

    Piece 0 of this item covers the first six files. ``check_file_chunk`` reads
    ``piece_length`` from the first of them, gets 74,735 bytes instead of
    524,288, and hashes a truncated buffer.
    """
    from torram_ng.cli import check_file_chunk

    info, root = archive_item
    piece_length = info["piece length"]
    first = root.joinpath(*info["files"][0]["path"])

    assert check_file_chunk(_piece_digests(info)[0], 0, piece_length, str(first)) is True
