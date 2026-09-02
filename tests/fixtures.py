"""Programmatic torrent fixtures.

Torrents and their content are generated at test time from a seeded, deterministic
byte source, so nothing large is committed and every edge case is constructed
explicitly rather than hoped for.

The bencode *encoder* here is hand-rolled on purpose: generating fixtures with the
same library the code under test parses with would let a library bug hide itself.
"""

import hashlib
import os


def bencode(obj):
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, bytes):
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, str):
        return bencode(obj.encode("utf-8"))
    if isinstance(obj, (list, tuple)):
        return b"l" + b"".join(bencode(x) for x in obj) + b"e"
    if isinstance(obj, dict):
        # bencode requires keys sorted as raw byte strings
        items = sorted(((k.encode("utf-8") if isinstance(k, str) else k), v) for k, v in obj.items())
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in items) + b"e"
    raise TypeError(f"cannot bencode {type(obj)!r}")


def det_bytes(n, seed="torram-ng"):
    """n deterministic, incompressible-looking bytes. Stable across runs and platforms."""
    out = bytearray()
    counter = 0
    while len(out) < n:
        out += hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        counter += 1
    return bytes(out[:n])


def make_torrent(name, files, piece_length, seed="torram-ng"):
    """Build a real v1 torrent plus the content it describes.

    ``files`` is a list of ``(path_components, length)``. A single entry whose
    path is ``None`` produces a single-file torrent.

    Returns ``(torrent_bytes, stream, file_contents)`` where ``stream`` is the
    concatenated piece stream and ``file_contents`` maps a path tuple to bytes.
    """
    single = len(files) == 1 and files[0][0] is None

    contents = {}
    stream = bytearray()
    for path, length in files:
        key = (name,) if single else tuple(path)
        data = det_bytes(length, seed="{}:{}".format(seed, "/".join(map(str, key))))
        contents[key] = data
        stream += data
    stream = bytes(stream)

    pieces = b"".join(hashlib.sha1(stream[i : i + piece_length]).digest() for i in range(0, len(stream), piece_length))

    info = {b"name": name.encode("utf-8"), b"piece length": piece_length, b"pieces": pieces}
    if single:
        info[b"length"] = files[0][1]
    else:
        info[b"files"] = [
            {
                b"length": length,
                b"path": [c.encode("utf-8") if isinstance(c, str) else c for c in path],
            }
            for path, length in files
        ]

    torrent = bencode({b"announce": b"http://example.invalid/announce", b"info": info})
    return torrent, stream, contents


def write_tree(root, contents, holes=None):
    """Materialise ``contents`` under ``root``.

    ``holes`` optionally maps a path tuple to a list of ``(offset, length)`` byte
    ranges to zero out, simulating a partial download.
    """
    holes = holes or {}
    for key, data in contents.items():
        target = os.path.join(str(root), *key)
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        buf = bytearray(data)
        for offset, length in holes.get(key, []):
            buf[offset : offset + length] = b"\0" * len(buf[offset : offset + length])
        with open(target, "wb") as fh:
            fh.write(bytes(buf))
    return root


# Torrent A -- multi-file gauntlet, 32 KiB pieces.
#
#   a.bin                     100000   not piece-aligned; next file starts mid-piece
#   empty.dat                      0   zero-length file
#   tiny.txt                      10   smaller than a piece
#   subdir/b.bin               70000   nested path
#   unicode-cafe-<jp>.bin      33000   non-ASCII path components
#
# Total 203010 over 32768-byte pieces => 7 pieces, final piece 6402 bytes (partial).
# Piece 3 covers the tail of a.bin, *all* of tiny.txt, and the head of subdir/b.bin,
# so it spans three real files at once.
TORRENT_A_PIECE_LENGTH = 32768
TORRENT_A_FILES = [
    (("a.bin",), 100000),
    (("empty.dat",), 0),
    (("tiny.txt",), 10),
    (("subdir", "b.bin"), 70000),
    (("unicode-café-日本語.bin",), 33000),
]

# Torrent B -- single file, exactly 4 x 64 KiB, so there is NO partial final piece.
TORRENT_B_PIECE_LENGTH = 65536
TORRENT_B_LENGTH = 4 * TORRENT_B_PIECE_LENGTH


def torrent_a():
    result = make_torrent("gauntlet", TORRENT_A_FILES, TORRENT_A_PIECE_LENGTH)
    stream = result[1]
    # Invariants this fixture exists to provide. Asserted at construction so the
    # guarantees hold without spending test cases on the generator itself.
    assert len(stream) == 203010
    assert len(stream) % TORRENT_A_PIECE_LENGTH == 6402, "must have a partial final piece"
    assert 3 * TORRENT_A_PIECE_LENGTH < 100000 < 100010 < 4 * TORRENT_A_PIECE_LENGTH, (
        "piece 3 must span a.bin, tiny.txt and subdir/b.bin"
    )
    return result


def torrent_b():
    result = make_torrent("aligned.bin", [(None, TORRENT_B_LENGTH)], TORRENT_B_PIECE_LENGTH)
    assert len(result[1]) % TORRENT_B_PIECE_LENGTH == 0, "must have no partial final piece"
    return result
