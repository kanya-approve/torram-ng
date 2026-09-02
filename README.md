# torram-ng

Recover torrent data by reconstructing files from fully and partially downloaded sources.

Given a `.torrent` file and one or more directories containing incomplete copies of its
contents, torram-ng identifies which pieces are intact by checking them against the piece
hashes in the torrent, and rebuilds the most complete output it can from what it finds.

If you have two dead torrents of the same release — one 75% done, the other 85% — the pieces
you are missing from one may be present in the other. Combined, they can add up to a complete
file.

> **Status: early.** This is a modernization of the unmaintained
> [`vbuell/torram`](https://github.com/vbuell/torram). This release makes the project
> installable, tested and continuously integrated; **the recovery engine itself is still the
> original 0.9.0 code and has known correctness defects.** Read
> [Known limitations](#known-limitations) before trusting it with anything you care about.

## Install

```sh
uv tool install git+https://github.com/kanya-approve/torram-ng
```

Or run it once without installing:

```sh
uvx --from git+https://github.com/kanya-approve/torram-ng torram-ng --help
```

Both `torram-ng` and `torram` are installed as commands. Python 3.8 or newer.

## Usage

```
torram-ng [-h] [--symlink] [--minsize MINSIZE] [-v] [-o OUTPUT_DIR] [-a]
          [-c] [-s] [--fileext FILE_EXT] [--version]
          torrentFile root
```

| Argument | Meaning |
|---|---|
| `torrentFile` | the `.torrent` to analyze |
| `root` | directory to search recursively for candidate files |
| `-o`, `--output_dir` | where to write recovered files (**required in practice**, see limitations) |
| `--minsize` | smallest file size to consider, in bytes. Defaults to 1 MiB, which silently excludes smaller files — pass `--minsize 0` |
| `-s`, `--autoskip` | skip prompting when there is only one option; `-ss` automates further |
| `-v`, `--verbose` | repeat for more detail (`-vv`, `-vvv`) |
| `-c`, `--use_color` | ANSI colour output |
| `--fileext` | suffix to append to output files, e.g. `.!qB` for incomplete qBittorrent files |

Example — scan two drives and rebuild into `./recovered`:

```sh
torram-ng show.torrent /mnt/disk1 -o ./recovered --minsize 0 -ss
```

After recovery, run a **force recheck** in your torrent client so it notices the files changed.

## How it works

A torrent describes its contents as one continuous byte stream, split into fixed-size pieces.
Each piece has a **SHA-1** hash stored in the `.torrent`. torram-ng walks the search directory,
picks out files whose size matches a file in the torrent, and hashes their pieces to find which
ones are intact. Where several sources each hold different good pieces, it can combine them.

## Known limitations

These are inherited from the original implementation and are tracked as
[issues](https://github.com/kanya-approve/torram-ng/issues). The most significant:

- **Pieces spanning file boundaries never verify.** In a multi-file torrent, a piece that
  straddles two files is read from only the first one, so it always fails. Even a perfect,
  complete source reports missing pieces. ([#3](https://github.com/kanya-approve/torram-ng/issues/3))
- **Files with no attributable piece default to being skipped.** A file that fits entirely
  inside a piece beginning in an earlier file gets no piece assigned to it, so it is reported
  `[0 of 0] (Bad)` and the suggested action is Skip. Interactively you can override this by
  choosing a candidate number; under `-s`/`-ss` it is dropped without prompting. On a real
  torrent this is not rare — 7 of the 12 files in Big Buck Bunny are affected.
  ([#3](https://github.com/kanya-approve/torram-ng/issues/3),
  [#11](https://github.com/kanya-approve/torram-ng/issues/11))
- **The merge path writes pieces at incorrect offsets** and never verifies the result, so
  combining sources can produce a corrupt file that reports success.
  ([#1](https://github.com/kanya-approve/torram-ng/issues/1))
- **Scanning several drives can lose candidates**, because hardlink de-duplication keys on the
  inode number without the device. ([#6](https://github.com/kanya-approve/torram-ng/issues/6))
- **`--minsize` defaults to 1 MiB**, so small-file torrents recover nothing unless you pass
  `--minsize 0`. ([#14](https://github.com/kanya-approve/torram-ng/issues/14))
- **`--symlink` does nothing** — it is parsed but never implemented.
  ([#17](https://github.com/kanya-approve/torram-ng/issues/17))
- **`-a` / `--autodetect_output_dir` cannot work**; it needs PyQt4, which has no Python 3 build.
  ([#18](https://github.com/kanya-approve/torram-ng/issues/18))
- **Performance does not scale.** The verification loop is roughly
  `candidates × pieces × files`, so large or many-file torrents are impractically slow.
  ([#21](https://github.com/kanya-approve/torram-ng/issues/21))
- Only BitTorrent v1 is supported. v2 and hybrid torrents are untested.

A [rewrite of the core](https://github.com/kanya-approve/torram-ng/issues/28) around a global
piece model is planned; it addresses most of the above structurally rather than one at a time.

The tool only ever reads from the directories you point it at, and writes solely to the output
directory. It does not modify your sources.

## Development

```sh
uv sync --all-groups
uv run pytest
uv run ruff check
uv run ruff format --check
```

Tests generate their own torrents and content deterministically, so nothing large is committed.
Two real torrents are included as parse-only fixtures — see [`tests/data/README.md`](tests/data/README.md).

Known bugs are covered by `xfail(strict=True)` tests referencing their issue number. They keep
CI green while documenting each defect as executable behaviour; when one is fixed its test
starts failing, which is the signal to remove the marker.

## Credits

Originally written by Volodymyr Buell as
[torram](https://github.com/vbuell/torram) (formerly torrent-upstart). See [NOTICE](NOTICE).

## License

[Apache-2.0](LICENSE). Note that the upstream project was published without a license; see
[#29](https://github.com/kanya-approve/torram-ng/issues/29).
