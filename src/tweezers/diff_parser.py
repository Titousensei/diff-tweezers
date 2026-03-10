#! /usr/bin/env python3

from collections import namedtuple
import re
import sys

HUNK_RE = re.compile(
    r"@@ -(?P<old_start>\d+)(?:,(?P<old_len>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_len>\d+))? @@"
)

def parse_hunk_header(header):
    m = HUNK_RE.match(header.strip())
    if not m:
        raise ValueError(f"Invalid hunk header: {header}")

    old_start = int(m.group("old_start"))
    new_start = int(m.group("new_start"))

    old_len = m.group("old_len")
    new_len = m.group("new_len")

    # If length omitted → default to 1
    old_len = int(old_len) if old_len else 1
    new_len = int(new_len) if new_len else 1

    return old_start, old_len, new_start, new_len

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

    def is_folded_marker(self, level):
        return self.is_folded

    def is_selected_marker(self):
        return self.is_selected

    def toggle_selection(self):
        pass

    def set_folded(self, value):
        self.is_folded = value

class FoldingChunk(FoldingPart):
    def __init__(self, label):
        super().__init__(label)
        self.lines = []
        
    def is_folded_marker(self, level):
        return self.is_folded and level == 1
        
    def toggle_selection(self):
        self.is_selected = not self.is_selected
    
    def _add_line(self, line):
        self.lines.append(line)

    def __str__(self):
        return "    *** FoldingChunk " + str(self.labels) + "\n    ... " + str(len(self.lines)) + " lines"


class FoldingFile(FoldingPart):
    def __init__(self, label):
        super().__init__(label)
        self.chunks = []
        
    def is_selected_marker(self):
        selected = sum(1 for c in self.chunks if c.is_selected)

        if selected == 0:
            return 0
        elif selected == len(self.chunks):
            return 1
        else:
            return 2

    def toggle_selection(self):
        all_selected = all(c.is_selected for c in self.chunks)

        new_state = not all_selected

        for chunk in self.chunks:
            chunk.is_selected = new_state

    def set_folded(self, value):
        for c in self.chunks:
            c.is_folded = value

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


def parse_diff(path, text):
    ret = FoldingDiff(path)

    current_file = None
    current_chunk = None

    for i, line in enumerate(text.split('\n')):
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

def build_patch(diff, selected=True):
    #left_patch = build_patch(diff, selected=False)
    #right_patch = build_patch(diff, selected=True)
    out = []
    for file in diff.files:
        write_file_block(out, file, include_selected=selected)
        
    return "\n".join(out) + "\n"


def write_file_block(out, file, include_selected):

    # Write file headers once
    wrote_header = False

    # Track delta from SKIPPED hunks to adjust new_start for subsequent hunks
    skipped_delta = 0

    for chunk in file.chunks:

        belongs = chunk.is_selected == include_selected

        original_header = chunk.labels[0]
        old_start, _, new_start, _ = parse_hunk_header(original_header)

        if belongs:
            if not wrote_header:
                for label in file.labels:
                    out.append(label)
                wrote_header = True

            # old_start is unchanged - it always refers to the original file
            # new_start needs adjustment for skipped hunks' deltas
            adj_new_start = new_start - skipped_delta

            real_old_len, real_new_len, delta = compute_chunk_stats(chunk)

            new_header = (
                f"@@ -{old_start},{real_old_len} "
                f"+{adj_new_start},{real_new_len} @@"
            )

            out.append(new_header)

            for line in chunk.lines:
                out.append(line)

        else:
            # Track delta from skipped hunks to adjust subsequent new_start values
            _, _, delta = compute_chunk_stats(chunk)
            skipped_delta += delta


def parse_hunk_header(header):
    m = HUNK_RE.match(header.strip())
    if not m:
        raise ValueError(f"Invalid hunk header: {header}")

    old_start = int(m.group("old_start"))
    new_start = int(m.group("new_start"))

    old_len = m.group("old_len")
    new_len = m.group("new_len")

    # If length omitted → default to 1
    old_len = int(old_len) if old_len else 1
    new_len = int(new_len) if new_len else 1

    return old_start, old_len, new_start, new_len


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


def build_chunk(old_start, new_start, lines):
    old_len = 0
    new_len = 0

    for line in lines:
        if line.startswith('-'):
            old_len += 1
        elif line.startswith('+'):
            new_len += 1
        else:
            old_len += 1
            new_len += 1

    header = f"@@ -{old_start},{old_len} +{new_start},{new_len} @@"

    new_chunk = FoldingChunk(header)
    new_chunk.lines = lines.copy()

    return new_chunk


def split_chunk(file, chunk):

    header = chunk.labels[0]
    old_start, old_len, new_start, new_len = parse_hunk_header(header)

    segments = []
    current = []
    current_type = None

    for line in chunk.lines:
        t = "mod" if line.startswith('-') or line.startswith('+') else "ctx"

        if current_type is None:
            current_type = t

        if t != current_type:
            segments.append((current_type, current))
            current = []
            current_type = t

        current.append(line)

    segments.append((current_type, current))

    # Now build new chunks
    new_chunks = []
    consumed_old = 0
    consumed_new = 0

    buffer = []

    for i, (typ, seg) in enumerate(segments):

        if typ == "ctx" and i > 0 and i < len(segments) - 1:
            # split boundary
            if buffer:
                new_chunks.append(build_chunk(
                    old_start + consumed_old,
                    new_start + consumed_new,
                    buffer
                ))

                # update consumed counts
                for line in buffer:
                    if not line.startswith('+'):
                        consumed_old += 1
                    if not line.startswith('-'):
                        consumed_new += 1

                buffer = []

        buffer.extend(seg)

    if buffer:
        new_chunks.append(build_chunk(
            old_start + consumed_old,
            new_start + consumed_new,
            buffer
        ))

    # Replace chunk
    idx = file.chunks.index(chunk)
    file.chunks[idx:idx+1] = new_chunks


if __name__ == '__main__':
    diff_obj = parse_diff(sys.argv[1])
    print(diff_obj)
