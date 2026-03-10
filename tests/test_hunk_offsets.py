"""Tests for hunk offset computation when building patches with selected hunks."""

import os
import subprocess
import tempfile

import pytest
from tweezers.diff_parser import (
    parse_diff,
    build_patch,
    parse_hunk_header,
    compute_chunk_stats,
    split_chunk,
)


# Sample diff with multiple hunks in one file
MULTI_HUNK_DIFF = """\
diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,5 +1,6 @@
 line1
 line2
+added_line_A
 line3
 line4
 line5
@@ -10,5 +11,6 @@
 line10
 line11
+added_line_B
 line12
 line13
 line14
@@ -20,5 +22,6 @@
 line20
 line21
+added_line_C
 line22
 line23
 line24
"""


class TestParseHunkHeader:
    def test_basic_header(self):
        old_start, old_len, new_start, new_len = parse_hunk_header("@@ -1,5 +1,6 @@")
        assert old_start == 1
        assert old_len == 5
        assert new_start == 1
        assert new_len == 6

    def test_header_with_offset(self):
        old_start, old_len, new_start, new_len = parse_hunk_header("@@ -10,5 +11,6 @@")
        assert old_start == 10
        assert old_len == 5
        assert new_start == 11
        assert new_len == 6


class TestComputeChunkStats:
    def test_addition_only(self):
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        chunk = diff.files[0].chunks[0]
        old_len, new_len, delta = compute_chunk_stats(chunk)
        # 5 context lines + 1 addition
        assert old_len == 5
        assert new_len == 6
        assert delta == 1


class TestBuildPatchAllSelected:
    """When all hunks are selected, patch should be equivalent to original."""

    def test_all_selected_preserves_structure(self):
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        # Select all chunks
        for file in diff.files:
            for chunk in file.chunks:
                chunk.is_selected = True

        patch = build_patch(diff, selected=True)

        # Should contain all three hunks with correct line counts from actual content
        # Each hunk has 5 context + 1 addition = old_len=5, new_len=6
        # But trailing empty line is included, so old_len=6, new_len=7
        assert "@@ -1," in patch
        assert "@@ -10," in patch
        assert "@@ -20," in patch
        assert "added_line_A" in patch
        assert "added_line_B" in patch
        assert "added_line_C" in patch


class TestBuildPatchPartialSelection:
    """Test offset adjustments when only some hunks are selected."""

    def test_select_first_hunk_only(self):
        """First hunk selected: no offset adjustment needed."""
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        diff.files[0].chunks[0].is_selected = True
        diff.files[0].chunks[1].is_selected = False
        diff.files[0].chunks[2].is_selected = False

        patch = build_patch(diff, selected=True)
        
        # First hunk should be unchanged
        assert "@@ -1,5 +1,6 @@" in patch
        assert "added_line_A" in patch
        # Other hunks should not be present
        assert "added_line_B" not in patch
        assert "added_line_C" not in patch

    def test_select_second_hunk_only(self):
        """Second hunk selected: should adjust new_start for skipped first hunk."""
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        diff.files[0].chunks[0].is_selected = False  # delta = +1 (skipped)
        diff.files[0].chunks[1].is_selected = True
        diff.files[0].chunks[2].is_selected = False

        patch = build_patch(diff, selected=True)
        
        # old_start should remain 10 (original file unchanged)
        # new_start should be 11 - 1 = 10 (adjusted for skipped hunk's delta)
        assert "@@ -10,5 +10,6 @@" in patch
        assert "added_line_B" in patch
        assert "added_line_A" not in patch
        assert "added_line_C" not in patch

    def test_select_third_hunk_only(self):
        """Third hunk selected: should adjust for two skipped hunks."""
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        diff.files[0].chunks[0].is_selected = False  # delta = +1
        diff.files[0].chunks[1].is_selected = False  # delta = +1
        diff.files[0].chunks[2].is_selected = True

        patch = build_patch(diff, selected=True)

        # old_start should remain 20 (original file unchanged)
        # new_start should be 22 - 2 = 20 (adjusted for two skipped hunks)
        assert "@@ -20," in patch
        assert "+20," in patch
        assert "added_line_C" in patch
        assert "added_line_A" not in patch
        assert "added_line_B" not in patch

    def test_select_first_and_third_hunks(self):
        """First and third hunks selected: third should adjust for skipped second."""
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        diff.files[0].chunks[0].is_selected = True
        diff.files[0].chunks[1].is_selected = False  # delta = +1 (skipped)
        diff.files[0].chunks[2].is_selected = True

        patch = build_patch(diff, selected=True)

        # First hunk unchanged
        assert "@@ -1," in patch
        # Third hunk: old_start=20, new_start=22-1=21
        assert "@@ -20," in patch
        assert "+21," in patch
        assert "added_line_A" in patch
        assert "added_line_C" in patch
        assert "added_line_B" not in patch


class TestBuildPatchWithDeletions:
    """Test offset computation with hunks that delete lines."""

    DELETION_DIFF = """\
diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,6 +1,4 @@
 line1
-deleted_A
-deleted_B
 line2
 line3
 line4
@@ -10,5 +8,6 @@
 line10
 line11
+added_line
 line12
 line13
 line14
"""

    def test_skip_deletion_hunk(self):
        """Skipping a deletion hunk should adjust new_start upward."""
        diff = parse_diff("test", self.DELETION_DIFF)
        diff.files[0].chunks[0].is_selected = False  # delta = -2 (removes 2 lines)
        diff.files[0].chunks[1].is_selected = True

        patch = build_patch(diff, selected=True)

        # old_start stays 10
        # new_start should be 8 - (-2) = 10
        assert "@@ -10," in patch
        assert "+10," in patch
        assert "added_line" in patch
        assert "deleted_A" not in patch


class TestBuildPatchNoneSelected:
    """Test that empty selection produces empty patch."""

    def test_none_selected(self):
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        # All chunks unselected (default)

        patch = build_patch(diff, selected=True)

        # Should be empty (just newline)
        assert patch.strip() == ""


class TestBuildPatchUnselected:
    """Test building patch from UNselected hunks (selected=False)."""

    def test_unselected_is_inverse_of_selected(self):
        """When first hunk selected, unselected patch should have hunks 2 and 3."""
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        diff.files[0].chunks[0].is_selected = True
        diff.files[0].chunks[1].is_selected = False
        diff.files[0].chunks[2].is_selected = False

        patch = build_patch(diff, selected=False)

        # Should contain hunks 2 and 3, not hunk 1
        assert "added_line_A" not in patch
        assert "added_line_B" in patch
        assert "added_line_C" in patch
        # Hunk 2 should have adjusted new_start (original 11, minus delta 1 from skipped hunk 1)
        assert "@@ -10," in patch
        assert "+10," in patch

    def test_unselected_with_middle_selected(self):
        """Skip middle hunk: unselected patch has hunks 1 and 3."""
        diff = parse_diff("test", MULTI_HUNK_DIFF)
        diff.files[0].chunks[0].is_selected = False
        diff.files[0].chunks[1].is_selected = True  # skipped in unselected patch
        diff.files[0].chunks[2].is_selected = False

        patch = build_patch(diff, selected=False)

        assert "added_line_A" in patch
        assert "added_line_B" not in patch
        assert "added_line_C" in patch


class TestMultipleFiles:
    """Test patches with multiple files."""

    MULTI_FILE_DIFF = """\
diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,4 @@
 line1
+added_in_file1
 line2
 line3
diff --git a/file2.py b/file2.py
--- a/file2.py
+++ b/file2.py
@@ -1,3 +1,4 @@
 lineA
+added_in_file2
 lineB
 lineC
"""

    def test_select_from_different_files(self):
        """Select hunk from file1, not from file2."""
        diff = parse_diff("test", self.MULTI_FILE_DIFF)
        diff.files[0].chunks[0].is_selected = True
        diff.files[1].chunks[0].is_selected = False

        patch = build_patch(diff, selected=True)

        assert "file1.py" in patch
        assert "added_in_file1" in patch
        assert "file2.py" not in patch
        assert "added_in_file2" not in patch

    def test_select_from_second_file_only(self):
        """Select hunk from file2, not from file1."""
        diff = parse_diff("test", self.MULTI_FILE_DIFF)
        diff.files[0].chunks[0].is_selected = False
        diff.files[1].chunks[0].is_selected = True

        patch = build_patch(diff, selected=True)

        assert "file1.py" not in patch
        assert "added_in_file1" not in patch
        assert "file2.py" in patch
        assert "added_in_file2" in patch


class TestMixedAdditionsAndDeletions:
    """Test hunks with both additions and deletions."""

    MIXED_DIFF = """\
diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,5 +1,5 @@
 line1
-old_line2
+new_line2
 line3
 line4
 line5
@@ -10,5 +10,7 @@
 line10
+added_A
+added_B
 line11
 line12
 line13
"""

    def test_skip_replacement_hunk(self):
        """First hunk replaces a line (delta=0), second adds lines."""
        diff = parse_diff("test", self.MIXED_DIFF)
        diff.files[0].chunks[0].is_selected = False  # delta = 0
        diff.files[0].chunks[1].is_selected = True

        patch = build_patch(diff, selected=True)

        # old_start=10, new_start should stay 10 (skipped hunk had delta=0)
        assert "@@ -10," in patch
        assert "+10," in patch
        assert "added_A" in patch
        assert "old_line2" not in patch
        assert "new_line2" not in patch


class TestSingleLineHunks:
    """Test hunks where line count is omitted (implies 1)."""

    SINGLE_LINE_DIFF = """\
diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -5 +5,2 @@
 line5
+added_line
"""

    def test_parse_single_line_header(self):
        """Parse header with omitted line counts."""
        old_start, old_len, new_start, new_len = parse_hunk_header("@@ -5 +5,2 @@")
        assert old_start == 5
        assert old_len == 1  # omitted means 1
        assert new_start == 5
        assert new_len == 2

    def test_both_omitted(self):
        """Parse header where both counts are omitted."""
        old_start, old_len, new_start, new_len = parse_hunk_header("@@ -5 +5 @@")
        assert old_start == 5
        assert old_len == 1
        assert new_start == 5
        assert new_len == 1


class TestSplitChunk:
    """Test the split_chunk function."""

    SPLITTABLE_DIFF = """\
diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,11 +1,13 @@
 line1
+added_A
 line2
 line3
 line4
+added_B
 line5
 line6
 line7
+added_C
 line8
 line9
"""

    def test_split_creates_multiple_chunks(self):
        """Splitting a chunk with context boundaries creates multiple chunks."""
        diff = parse_diff("test", self.SPLITTABLE_DIFF)
        file = diff.files[0]
        original_chunk = file.chunks[0]

        assert len(file.chunks) == 1

        split_chunk(file, original_chunk)

        # Should now have 3 chunks (split at context lines between modifications)
        assert len(file.chunks) == 3

    def test_split_chunks_have_correct_content(self):
        """Each split chunk contains the right lines."""
        diff = parse_diff("test", self.SPLITTABLE_DIFF)
        file = diff.files[0]
        split_chunk(file, file.chunks[0])

        # First chunk should have added_A
        chunk1_content = "\n".join(file.chunks[0].lines)
        assert "added_A" in chunk1_content
        assert "added_B" not in chunk1_content

        # Second chunk should have added_B
        chunk2_content = "\n".join(file.chunks[1].lines)
        assert "added_B" in chunk2_content
        assert "added_A" not in chunk2_content

        # Third chunk should have added_C
        chunk3_content = "\n".join(file.chunks[2].lines)
        assert "added_C" in chunk3_content

    def test_split_chunks_can_be_selected_independently(self):
        """After splitting, chunks can be individually selected."""
        diff = parse_diff("test", self.SPLITTABLE_DIFF)
        file = diff.files[0]
        split_chunk(file, file.chunks[0])

        # Select only the middle chunk
        file.chunks[0].is_selected = False
        file.chunks[1].is_selected = True
        file.chunks[2].is_selected = False

        patch = build_patch(diff, selected=True)

        assert "added_B" in patch
        assert "added_A" not in patch
        assert "added_C" not in patch


class TestGitApplyIntegration:
    """Integration tests that verify patches actually apply with git."""

    ORIGINAL_FILE = "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\n"

    # This diff adds a line after line2 and another after line7
    # Hunk 1: lines 1-5, adds 1 line (delta=+1)
    # Hunk 2: lines 6-10, adds 1 line (delta=+1)
    # Note: no trailing newline after last line to avoid parser adding empty line
    FULL_DIFF = (
        "diff --git a/testfile.txt b/testfile.txt\n"
        "--- a/testfile.txt\n"
        "+++ b/testfile.txt\n"
        "@@ -1,5 +1,6 @@\n"
        " line1\n"
        " line2\n"
        "+added_after_2\n"
        " line3\n"
        " line4\n"
        " line5\n"
        "@@ -6,5 +7,6 @@\n"
        " line6\n"
        " line7\n"
        "+added_after_7\n"
        " line8\n"
        " line9\n"
        " line10"  # no trailing \n
    )

    @pytest.fixture
    def git_repo(self):
        """Create a temporary git repo with the test file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmpdir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmpdir, capture_output=True
            )

            # Create and commit original file
            filepath = os.path.join(tmpdir, "testfile.txt")
            with open(filepath, "w") as f:
                f.write(self.ORIGINAL_FILE)

            subprocess.run(["git", "add", "testfile.txt"], cwd=tmpdir)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=tmpdir)

            yield tmpdir

    def test_full_patch_applies(self, git_repo):
        """Full patch (all hunks selected) should apply cleanly."""
        diff = parse_diff("test", self.FULL_DIFF)
        for file in diff.files:
            for chunk in file.chunks:
                chunk.is_selected = True

        patch = build_patch(diff, selected=True)

        result = subprocess.run(
            ["git", "apply", "--check", "-"],
            input=patch.encode(),
            cwd=git_repo,
            capture_output=True
        )
        assert result.returncode == 0, f"Patch failed: {result.stderr.decode()}"

    def test_first_hunk_only_applies(self, git_repo):
        """Selecting only first hunk should produce an applicable patch."""
        diff = parse_diff("test", self.FULL_DIFF)
        diff.files[0].chunks[0].is_selected = True
        diff.files[0].chunks[1].is_selected = False

        patch = build_patch(diff, selected=True)

        result = subprocess.run(
            ["git", "apply", "--check", "-"],
            input=patch.encode(),
            cwd=git_repo,
            capture_output=True
        )
        assert result.returncode == 0, f"Patch failed: {result.stderr.decode()}"

    def test_second_hunk_only_applies(self, git_repo):
        """Selecting only second hunk should produce an applicable patch."""
        diff = parse_diff("test", self.FULL_DIFF)
        diff.files[0].chunks[0].is_selected = False
        diff.files[0].chunks[1].is_selected = True

        patch = build_patch(diff, selected=True)

        result = subprocess.run(
            ["git", "apply", "--check", "-"],
            input=patch.encode(),
            cwd=git_repo,
            capture_output=True
        )
        assert result.returncode == 0, f"Patch failed: {result.stderr.decode()}"

    def test_apply_then_apply_remaining(self, git_repo):
        """Apply selected, then apply unselected - should equal full patch."""
        diff = parse_diff("test", self.FULL_DIFF)
        diff.files[0].chunks[0].is_selected = True
        diff.files[0].chunks[1].is_selected = False

        # Apply first hunk
        patch1 = build_patch(diff, selected=True)
        result = subprocess.run(
            ["git", "apply", "-"],
            input=patch1.encode(),
            cwd=git_repo,
            capture_output=True
        )
        assert result.returncode == 0, f"First patch failed: {result.stderr.decode()}"

        # Apply second hunk (from unselected)
        patch2 = build_patch(diff, selected=False)
        result = subprocess.run(
            ["git", "apply", "-"],
            input=patch2.encode(),
            cwd=git_repo,
            capture_output=True
        )
        assert result.returncode == 0, f"Second patch failed: {result.stderr.decode()}"

        # Verify final file content
        filepath = os.path.join(git_repo, "testfile.txt")
        with open(filepath) as f:
            content = f.read()

        assert "added_after_2" in content
        assert "added_after_7" in content

