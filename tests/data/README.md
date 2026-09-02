# Real torrent fixtures

`libtorrent/` holds the vendored adversarial corpus from the reference
BitTorrent implementation -- see its own [README](libtorrent/README.md).
The two torrents below are real-world v1 examples kept alongside it.

Torrent *metadata only* — no content is downloaded, so the test suite stays offline and fast.
Both are freely redistributable and were chosen because they exercise different real-world shapes.

## `debian-13.6.0-amd64-netinst.iso.torrent`

Official Debian installer torrent, from <https://cdimage.debian.org/debian-cd/current/amd64/bt-cd/>.

- single-file torrent
- 256 KiB pieces, 3020 pieces, 791,674,880 bytes
- exercises the single-file code path at a realistic piece count

## `BigBuckBunny_124_archive.torrent`

Internet Archive item <https://archive.org/details/BigBuckBunny_124>. Big Buck Bunny is
(c) Blender Foundation, released under Creative Commons Attribution 3.0.

- multi-file torrent, 12 files, 441,396,841 bytes total
- 512 KiB pieces, 842 pieces
- **9 of the 12 files are smaller than one piece.** Files 0-7 total just 62,917 bytes against a
  512 KiB piece length, so the *first piece alone spans nine files* — a natural real-world
  reproducer for the spanning-piece bug

## Verifying against real content

`tests/test_network.py` checks our piece arithmetic against hashes produced by
other implementations, using content fetched over plain HTTPS:

| Source | What it fetches | Why |
|---|---|---|
| Debian netinst ISO | first 4 MiB via HTTP `Range` | 16 real pieces without a 791 MB download; the mirror sends `Accept-Ranges: bytes`, and the URL is version-pinned rather than using the moving `current/` symlink |
| archive.org `alicesadventures19033gut` | all 63 files, 3.8 MB, in parallel | Project Gutenberg's *Alice's Adventures in Wonderland*, public domain. 62 of 63 files are smaller than the 512 KiB piece length, so nearly every piece spans several files |

The archive.org torrent is fetched at test time rather than committed, so the
metadata and the content cannot drift apart if the item is ever re-derived.

These are marked `network` and deselected by default. Run them with
`uv run pytest -m network`. CI runs them in a separate workflow so an external
outage cannot block a pull request.
