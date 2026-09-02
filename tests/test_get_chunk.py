"""Tests for the global-offset map.

``get_chunk`` translates a global byte offset in the concatenated piece stream
into ``(file_index, offset_within_file)``. It is the most correctness-critical
function in the codebase, and the docstring examples shipped with it were never
executed -- one of them is simply wrong, which these tests pin down.
"""

import pytest

from torram_ng.cli import get_chunk


def test_empty_file_list():
    assert get_chunk([], 0) == (0, 0)


def test_offset_zero_is_start_of_first_file():
    assert get_chunk([100], 0) == (0, 0)


def test_offset_inside_first_file():
    assert get_chunk([100], 50) == (0, 50)


def test_offset_one_past_the_end_rolls_to_the_next_index():
    """The shipped docstring claims (0, 0) here. It is wrong: an offset equal to
    the total length is one past the end of file 0, so the index advances."""
    assert get_chunk([100], 100) == (1, 0)


def test_exact_boundary_between_files():
    assert get_chunk([50, 50, 30], 50) == (1, 0)
    assert get_chunk([50, 50, 30], 100) == (2, 0)


def test_offset_inside_a_later_file():
    assert get_chunk([50, 50, 30], 75) == (1, 25)
    assert get_chunk([50, 50, 30], 110) == (2, 10)


@pytest.mark.xfail(
    strict=True,
    reason="zero-length files are unreachable in the offset map -- issue #11",
)
def test_zero_length_file_is_addressable():
    """A zero-length file occupies no bytes but is still a real entry.

    The accumulator only advances on ``file_offset + filesize > global_offset``,
    which a zero-length file can never satisfy, so index 1 below is skipped
    entirely and the function reports index 2.
    """
    assert get_chunk([10, 0, 10], 10) == (1, 0)
