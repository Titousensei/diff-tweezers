#! /usr/bin/env python3

from collections import namedtuple
import curses
import re
import sys

HUNK_RE = re.compile(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@")


# Diff struct:
# - file ("diff", "---", "+++")
#     - chunk "@@"
#         - lines

PREFIX_DIFF = "diff "
PREFIX_PLUS = "+++ "
PREFIX_MINUS = "--- "
PREFIX_CHUNK = "@@ "

class FoldingPart:
    def __init__(self, label):
        self.labels = [ label ]
        self.is_folded = False
        self.is_selected = False


class FoldingChunk(FoldingPart):
    def __init__(self, label):
        super().__init__(label)
        self.lines = []
        
    def _add_line(self, line):
        self.lines.append(line)

    def __str__(self):
        return "    *** FoldingChunk " + str(self.labels) + "\n    ... " + str(len(self.lines)) + " lines"

class FoldingFile(FoldingPart):
    def __init__(self, label):
        super().__init__(label)
        self.chunks = []

    def _add_label(self, line):
        self.labels.append(line)
            
    def _add_chunk(self, line):
        self.chunks.append(FoldingChunk(line))

    def _add_line(self, line):
        self.chunks[-1]._add_line(line)

    def __str__(self):
        return "  *** FoldingFile\n" + "\n".join("  " + x for x in self.labels) + "\n" + "\n".join(str(x) for x in self.chunks)


class FoldingDiff(FoldingPart):
    def __init__(self, label):
        super().__init__(label)
        self.files = []

    def _add_file(self, line):
        self.files.append(FoldingFile(line))

    def _add_label(self, line):
        if self.files:
            self.files[-1]._add_label(line)
        else:
            self.labels.append(line)
        

    def _add_chunk(self, line):
        self.files[-1]._add_chunk(line)

    def _add_line(self, line):
        self.files[-1]._add_line(line)

    def __str__(self):
        return "*** FoldingDiff\n" + "\n".join(self.labels) + "\n" + "\n".join(str(x) for x in self.files)


def parse_diff(path):
    ret = FoldingDiff(path)

    current_file = None
    current_chunk = None

    with open(path) as f:
        for i, line in enumerate(f):
            line = line.rstrip("\n")

            if line.startswith(PREFIX_DIFF):
                ret._add_file(line)
                current_file = ret.files[-1]
                current_chunk = None

            elif line.startswith(PREFIX_MINUS) and current_chunk is None:
                # --- file header
                ret._add_label(line)

            elif line.startswith(PREFIX_PLUS) and current_chunk is None:
                # +++ file header
                ret._add_label(line)

            elif line.startswith(PREFIX_CHUNK):
                ret._add_chunk(line)
                current_chunk = current_file.chunks[-1]

            else:
                # Inside chunk content
                if current_chunk is not None:
                    current_chunk._add_line(line)
                else:
                    ret._add_label(line)

    return ret


# -----------------------------
# Writing Split Diffs
# -----------------------------

def write_split(diff, file_a_path, file_b_path):
    with open(file_a_path, "w") as fa, open(file_b_path, "w") as fb:

        for file in diff.files:

            has_left = any(not c.is_selected for c in file.chunks)
            has_right = any(c.is_selected for c in file.chunks)

            if has_left:
                write_file_block(fa, file, include_selected=False)

            if has_right:
                write_file_block(fb, file, include_selected=True)


def write_file_block(out, file, include_selected):
    """
    include_selected=True  -> right.patch
    include_selected=False -> left.patch
    """

    # Write file headers once
    wrote_header = False

    cumulative_delta = 0

    for chunk in file.chunks:

        belongs = chunk.is_selected == include_selected

        original_header = chunk.labels[0]
        old_start, old_len, new_start, new_len = parse_hunk_header(original_header)

        if belongs:
            if not wrote_header:
                for label in file.labels:
                    out.write(label + "\n")
                wrote_header = True

            adj_old_start = old_start + cumulative_delta
            adj_new_start = new_start + cumulative_delta

            real_old_len, real_new_len, delta = compute_chunk_stats(chunk)

            new_header = (
                f"@@ -{adj_old_start},{real_old_len} "
                f"+{adj_new_start},{real_new_len} @@"
            )

            out.write(new_header + "\n")

            for line in chunk.lines:
                out.write(line + "\n")

            cumulative_delta += delta

        else:
            # Important: do NOT change cumulative_delta
            # because this chunk does not exist in this patch.
            pass


def parse_hunk_header(header):
    m = HUNK_RE.search(header)
    if not m:
        raise ValueError(f"Invalid hunk header: {header}")
    return tuple(map(int, m.groups()))


def compute_chunk_stats(chunk):
    old_len = 0
    new_len = 0

    for line in chunk.lines:
        if line.startswith("-"):
            old_len += 1
        elif line.startswith("+"):
            new_len += 1
        else:
            old_len += 1
            new_len += 1

    delta = new_len - old_len
    return old_len, new_len, delta


if __name__ == '__main__':
    diff_obj = parse_diff(sys.argv[1])
    print(diff_obj)
