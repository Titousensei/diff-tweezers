#! /usr/bin/env python3

import curses
import sys
from diff_parser import (
    compute_chunk_stats,
    compute_chunk_stats,
    parse_diff,
    parse_hunk_header,
    write_file_block,
    write_split,
)

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


def get_current_file(rows, offset, diff):
    obj, _, _ = rows[offset]

    # If it's a file, return it
    if hasattr(obj, "chunks"):
        return obj

    # Otherwise find its parent file
    for f in diff.files:
        if obj in f.chunks:
            return f

    return None

# -----------------------------
# Flatten Structured Diff
# -----------------------------

def flatten(diff):
    rows = []

    for file in diff.files:

        if file.is_folded:
            # Only show the first label (diff line)
            if file.labels:
                rows.append((file, file.labels[0], 0))
            continue

        # Unfolded: show all labels
        for label in file.labels:
            rows.append((file, label, 0))

        for chunk in file.chunks:

            rows.append((chunk, chunk.labels[0], 1))

            if not chunk.is_folded:
                for line in chunk.lines:
                    rows.append((chunk, line, 2))

    return rows

# -----------------------------
# Curses UI
# -----------------------------

def run_ui(scr, diff_path, output_prefix):
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
    last_key = None
    sticky_file = None

    while True:
        scr.erase()
        max_y, max_x = scr.getmaxyx()
        max_y -= 2
        max_x -= 2

        scr.border(0)

        rows = flatten(diff)
        sticky_file = get_current_file(rows, offset, diff)

        # Reserve one line for sticky header
        visible = rows[offset:offset + max_y - 1]

        if sticky_file:
            sticky_line = sticky_file.labels[0]

            if len(sticky_line) > max_x:
                sticky_line = sticky_line[:max_x]

            scr.addstr(1, 3, sticky_line, curses.A_REVERSE | curses.A_BOLD)

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
            scr.addstr(i + 2, 1, text, style)

            if getattr(obj, "is_selected", False):
                scr.addstr(i + 1, 0, "=")

        status = (
            f"[space] select  [tab] fold  [c] cut  [q] quit"
            f"    Selected chunks: {selected_count}"
        )

        scr.addstr(0, 2, status[:max_x])

        scr.move(cursor + 2, 1)
        scr.refresh()

        c = scr.getch()

        # -------------------------
        # Vim double-key handling
        # -------------------------

        if last_key == ord('g') and c == ord('g'):
            offset = 0
            cursor = 0
            last_key = None
            continue

        if c == ord('g'):
            last_key = ord('g')
            continue
        else:
            last_key = None

        # -------------------------
        # Quit
        # -------------------------

        if c == ord('q'):
            break

        # -------------------------
        # Movement (Arrow + Vim)
        # -------------------------

        elif c == curses.KEY_UP or c == ord('k'):
            if cursor > 0:
                cursor -= 1
            elif offset > 0:
                offset -= 1

        elif c == curses.KEY_DOWN or c == ord('j'):
            if cursor < len(rows) - offset - 1 and cursor < max_y - 1:
                cursor += 1
            elif offset + max_y < len(rows):
                offset += 1

        elif c == curses.KEY_NPAGE or c == 4:  # Ctrl-d
            offset = min(offset + max_y // 2, max(0, len(rows) - max_y))

        elif c == curses.KEY_PPAGE or c == 21:  # Ctrl-u
            offset = max(offset - max_y // 2, 0)

        elif c == curses.KEY_HOME:
            offset = 0
            cursor = 0

        elif c == curses.KEY_END or c == ord('G'):
            offset = max(0, len(rows) - max_y)
            cursor = min(max_y - 1, len(rows) - 1)

        # -------------------------
        # Actions
        # -------------------------

        elif c == ord(" "):
            obj, _, _ = rows[offset + cursor]
            if hasattr(obj, "lines"):
                obj.is_selected = not obj.is_selected

        elif c == ord("c"):
            write_split(
                diff,
                f"{output_prefix}-left.patch",
                f"{output_prefix}-right.patch"
            )
            break

        # -------------------------
        # Fold control
        # -------------------------

        elif c == curses.KEY_RIGHT or c == ord('l'):
            obj, _, _ = rows[offset + cursor]
            if hasattr(obj, "is_folded") and obj.is_folded:
                obj.is_folded = False

        elif c == curses.KEY_LEFT or c == ord('h'):
            obj, _, _ = rows[offset + cursor]
            if hasattr(obj, "is_folded") and not obj.is_folded:

                # Find header index BEFORE folding
                header_index = None
                for idx, (o, _, level) in enumerate(rows):
                    if o is obj and level in (0, 1):
                        header_index = idx
                        break

                obj.is_folded = True

                # Recompute rows after folding
                rows = flatten(diff)

                if header_index is not None:
                    # Move cursor to header position
                    if header_index < offset:
                        offset = header_index
                        cursor = 0
                    elif header_index >= offset + max_y:
                        offset = header_index - max_y + 1
                        cursor = max_y - 1
                    else:
                        cursor = header_index - offset


if __name__ == "__main__":
    curses.wrapper(main)
