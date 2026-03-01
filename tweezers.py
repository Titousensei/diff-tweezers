#! /usr/bin/env python3

import curses
import sys
from diff_parser import parse_diff


# -----------------------------
# Rendering Helpers
# -----------------------------

FOLD_MARKER = "▶ "
UNFOLD_MARKER = "  "


def get_style(line):
    if line.startswith("diff "):
        return curses.A_BOLD
    elif line.startswith("--- "):
        return curses.A_BOLD | curses.color_pair(1)
    elif line.startswith("+++ "):
        return curses.A_BOLD | curses.color_pair(2)
    elif line.startswith("@@"):
        return curses.A_BOLD | curses.color_pair(4)
    elif line.startswith("-"):
        return curses.color_pair(1)
    elif line.startswith("+"):
        return curses.color_pair(2)
    return curses.A_DIM


# -----------------------------
# Flatten Structured Diff
# -----------------------------

def flatten(diff):
    rows = []

    for file in diff.files:
        for label in file.labels:
            rows.append((file, label, 0))

        if not file.is_folded:
            for chunk in file.chunks:
                for label in chunk.labels:
                    rows.append((chunk, label, 1))

                if not chunk.is_folded:
                    for line in chunk.lines:
                        rows.append((chunk, line, 2))

    return rows


# -----------------------------
# Writing Split Diffs
# -----------------------------

def write_split(diff, file_a_path, file_b_path):
    """
    file_a: unselected chunks
    file_b: selected chunks
    """

    with open(file_a_path, "w") as fa, open(file_b_path, "w") as fb:

        for file in diff.files:

            chunks_a = [c for c in file.chunks if not c.is_selected]
            chunks_b = [c for c in file.chunks if c.is_selected]

            if chunks_a:
                write_file_block(fa, file, chunks_a)

            if chunks_b:
                write_file_block(fb, file, chunks_b)


def write_file_block(out, file, chunks):
    for label in file.labels:
        out.write(label + "\n")

    for chunk in chunks:
        for label in chunk.labels:
            out.write(label + "\n")
        for line in chunk.lines:
            out.write(line + "\n")


# -----------------------------
# Curses UI
# -----------------------------

def main(scr):
    curses.noecho()
    curses.cbreak()
    scr.keypad(True)

    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_BLUE, -1)

    if len(sys.argv) < 2:
        print("Usage: tweezers.py <diff_file>")
        sys.exit(1)

    diff_path = sys.argv[1]
    diff = parse_diff(diff_path)

    offset = 0
    cursor = 0

    while True:
        scr.erase()
        max_y, max_x = scr.getmaxyx()
        max_y -= 2
        max_x -= 2

        scr.border(0)

        rows = flatten(diff)
        visible = rows[offset:offset + max_y]

        selected_count = sum(
            1
            for file in diff.files
            for chunk in file.chunks
            if chunk.is_selected
        )

        for i, (obj, line, level) in enumerate(visible):
            indent = "  " * level

            # Fold marker
            marker = ""
            if hasattr(obj, "chunks"):  # file
                marker = FOLD_MARKER if obj.is_folded else UNFOLD_MARKER
            elif hasattr(obj, "lines") and level == 1:  # chunk header
                marker = FOLD_MARKER if obj.is_folded else UNFOLD_MARKER

            text = indent + marker + line

            if len(text) > max_x:
                text = text[:max_x]

            style = get_style(line)
            scr.addstr(i + 1, 1, text, style)

            if getattr(obj, "is_selected", False):
                scr.addstr(i + 1, 0, "=")

        status = (
            f"[space] select  [tab] fold  [c] cut  [q] quit"
            f"    Selected chunks: {selected_count}"
        )

        scr.addstr(0, 2, status[:max_x])

        scr.move(cursor + 1, 1)
        scr.refresh()

        c = scr.getch()

        if c == ord("q"):
            break

        elif c == ord(" "):
            obj, _, _ = rows[offset + cursor]
            if hasattr(obj, "lines"):
                obj.is_selected = not obj.is_selected

        elif c == ord("\t"):
            obj, _, _ = rows[offset + cursor]
            if hasattr(obj, "is_folded"):
                obj.is_folded = not obj.is_folded

        elif c == ord("c"):
            write_split(diff, "left.patch", "right.patch")
            break

        elif c == curses.KEY_UP:
            if cursor > 0:
                cursor -= 1
            elif offset > 0:
                offset -= 1

        elif c == curses.KEY_DOWN:
            if cursor < len(visible) - 1:
                cursor += 1
            elif offset + max_y < len(rows):
                offset += 1

        elif c == curses.KEY_NPAGE:
            offset = min(offset + max_y, max(0, len(rows) - max_y))

        elif c == curses.KEY_PPAGE:
            offset = max(offset - max_y, 0)


if __name__ == "__main__":
    curses.wrapper(main)
