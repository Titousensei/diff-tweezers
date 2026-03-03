#! /usr/bin/env python3

import curses
import sys
from diff_parser import (
    compute_chunk_stats,
    compute_chunk_stats,
    parse_diff,
    parse_hunk_header,
    split_chunk,
    FoldingChunk,
    FoldingFile,
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


def find_parent_file(diff, chunk):
    for f in diff.files:
        if chunk in f.chunks:
            return f
            
    return None


def get_current_file(rows, offset, diff):
    obj, _, _ = rows[offset]

    # If it's a file, return it
    if isinstance(obj, FoldingFile):
        return obj
        
    return find_parent_file(diff, obj)


def move_to_next_file(rows, start_index):
    start_obj, _, _ = rows[start_index]
    for i in range(start_index + 1, len(rows)):
        obj, _, _ = rows[i]
        if isinstance(obj, FoldingFile) and start_obj != obj:
            return i
    return start_index

    
def move_to_prev_file(rows, start_index):
    start_obj, _, _ = rows[start_index]
    top_i = 0
    for i in range(start_index - 1, -1, -1):
        obj, _, _ = rows[i]
        if isinstance(obj, FoldingFile) and start_obj != obj:
            top_i = i
        elif top_i:
            break
    return top_i


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


def reposition(new_pos, max_y, total_rows):
    half = max_y // 2

    offset = max(0, new_pos - half)

    # Clamp so we don't scroll past bottom
    if offset + max_y > total_rows:
        offset = max(0, total_rows - max_y)

    cursor = new_pos - offset

    return offset, cursor

# -----------------------------
# Curses UI
# -----------------------------

def run_ui(scr, diff):
    curses.noecho()
    curses.cbreak()
    scr.keypad(True)

    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_BLUE, -1)

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
            marker = FOLD_MARKER if obj.is_folded_marker(level) else UNFOLD_MARKER

            text = indent + marker + line

            if len(text) > max_x:
                text = text[:max_x]

            style = get_style(line)
            scr.addstr(i + 2, 1, text, style)

            sel_marker = obj.is_selected_marker()
            if sel_marker == 1:
                scr.addstr(i + 2, 0, "=")
            elif sel_marker == 2:
                scr.addstr(i + 2, 0, ":")

        status = (
            f"[space] select  [c] cut  [q] quit"
            f"    Selected: {selected_count}"
            f"    {diff.labels}"
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

        elif c == ord('}') or c == ord(']'):
            new_pos = move_to_next_file(rows, offset + cursor)
            offset, cursor = reposition(new_pos, max_y, len(rows))

        elif c == ord('{') or c == ord('['):
            new_pos = move_to_prev_file(rows, offset + cursor)
            offset, cursor = reposition(new_pos, max_y, len(rows))

        # -------------------------
        # Actions
        # -------------------------

        elif c == ord(' '):
            obj, _, _ = rows[offset + cursor]
            obj.toggle_selection()

        elif c == ord('c'):
            return

        elif c == ord('s'):
            obj, _, _ = rows[offset + cursor]
            if isinstance(obj, FoldingChunk):
                parent_file = find_parent_file(diff, obj)
                split_chunk(parent_file, obj)
        
        # -------------------------
        # Fold control
        # -------------------------

        elif c == curses.KEY_RIGHT or c == ord('l'):
            obj, _, _ = rows[offset + cursor]
            obj.set_folded(False)

        elif c == curses.KEY_LEFT or c == ord('h'):
            obj, _, _ = rows[offset + cursor]
            if not obj.is_folded:

                # Find header index BEFORE folding
                header_index = None
                for idx, (o, _, level) in enumerate(rows):
                    if o is obj and level in (0, 1):
                        header_index = idx
                        break

                obj.set_folded(True)

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
