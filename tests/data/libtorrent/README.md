# libtorrent test torrent corpus

Vendored from [arvidn/libtorrent](https://github.com/arvidn/libtorrent),
`test/test_torrents/`, which is BSD-3-Clause (see [LICENSE](LICENSE)).
Copyright (c) 2003-2020, Arvid Norberg.

100 torrents, 56 KB, metadata only. This is an adversarial corpus assembled by the
reference BitTorrent implementation, so it covers hostile and degenerate shapes
far better than anything hand-written:

| Group | Examples | Relevant to |
|---|---|---|
| path escapes | `absolute_filename`, `parent_path`, `hidden_parent_path`, `backslash_path`, `slash_path*` | path traversal |
| zero-length files | `empty-files-1`..`5`, `empty_path`, `empty_path_multi` | zero-length handling |
| BEP 47 padding | `pad_file`, `pad_file_no_path` | pad-file handling |
| malformed | `invalid_*`, `negative_*`, `missing_*`, `no_*` | parser hardening |
| BitTorrent v2 | `v2`, `v2_hybrid`, `v2_only`, `v2_multiple_files`, ~30 more | v1/v2 compatibility |
| duplicates | `duplicate_files`, `duplicate_files2` | duplicate path handling |
| scale | `many_pieces`, `large_piece_size` | large-torrent behaviour |
| alignment | `unaligned_pieces`, `single_multi_file` | piece/file boundary handling |
| symlinks | `symlink1`, `symlink2`, `overlapping_symlinks` | symlink entries |

Eight of the upstream torrents over 10 KB are not vendored. Seven were v2 files
that the current parser cannot decode at all, so they added 611 KB of bulk and no
coverage; the eighth, `large.torrent`, is a single-file torrent already covered by
smaller cases. Dropping them took the corpus from 767 KB to 56 KB. Twenty-six
smaller v2 torrents remain for the compatibility work.

A git submodule was considered and rejected: libtorrent checks out at 111 MB, and
a submodule would also complicate sdist builds and require `submodules: true` on
every checkout -- a poor trade for 56 KB of fixtures.

These carry no content, so they exercise parsing and structure only. Tests that
need real bytes to hash against real piece hashes still use the generated
fixtures in `tests/fixtures.py`.
