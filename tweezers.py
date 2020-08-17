#! /usr/bin/env python3

from collections import namedtuple
import curses
import sys

# Diff struct:
# - file ("diff", "---", "+++")
#   - chunk "@@"
#     - lines

class FoldingDiff:
  def __init__(self, lines, files, chunks):
    self.lines = lines
    self.files = files
    self.chunks = chunks
    self._folded = set()
    self._selected = set()
    self.offset = 0

  def __iter__(self):
    self.i = self.offset
    return self

  def __next__(self):
    i = self.i
    if i >= len(self.lines):
      raise StopIteration
    self.i += 1

    ret = self.lines[i]
    if i in self._folded:
      ret = ">" + ret
      try:
        pos = self.chunks.index(i)
        self.i = self.chunks[pos + 1]
      except:
        pass
    return ret, i, (i in self._selected)

  def is_foldable(self, i):
      l = self.lines[i]
      return l.startswith('diff ') or l.startswith('@@ ')

  def find_foldable_before(self, i):
    while i > 0 and not self.is_foldable(i):
      i -= 1
    return i

  def find_foldable_after(self, i):
    m = len(self.lines)
    while i < m and not self.is_foldable(i):
      i += 1
    return i

  def toggle_fold(self, orig_i):
    if self.is_foldable(orig_i):
      i = orig_i
    else:
      i = self.find_foldable_before(orig_i)
    if i in self._folded:
      self._folded.remove(i)
    else:
      self._folded.add(i)
    return orig_i - i

  def toggle_select(self, i):
    if i in self._selected:
      self._selected.remove(i)
    else:
      self._selected.add(i)

  @classmethod
  def from_file(cls, path):
    lines = []
    files = []
    chunks = []
    with open(path) as f:
      for i, l in enumerate(f):
        lines.append(l[:-1])
        if l.startswith('diff '):
          files.append(i)
        elif l.startswith('@@ '):
          chunks.append(i)

    return cls(lines, files, chunks)


def get_style(l):
  if l.startswith('diff ') or l.startswith('>diff '):
    return curses.A_BOLD # COLOR_WHITE
  elif l.startswith('--- '):
    return curses.A_BOLD | curses.color_pair(1) # COLOR_RED
  elif l.startswith('+++ '):
    return curses.A_BOLD | curses.color_pair(2) # COLOR_GREEN
  elif l.startswith('@@ ') or l.startswith('>@@ '):
    return curses.A_BOLD | curses.color_pair(4) # COLOR_BLUE
  elif l.startswith('-'):
    return curses.color_pair(1) # COLOR_RED
  elif l.startswith('+'):
    return curses.color_pair(2) # COLOR_GREEN
  return curses.A_DIM


def main(scr):
  curses.noecho()
  # make curses give nice values (such as curses.KEY_LEFT)
  scr.keypad(True)
  scr.clear()

  curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
  curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
  curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
  curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
  curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
  curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
  curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)

  diff_path = sys.argv[1]
  d = FoldingDiff.from_file(diff_path)

  cur_y = 0
  while True:
    # First, clear the screen
    scr.erase()
    my, mx = scr.getmaxyx()
    mx -= 2
    my -= 2

    # print on screen here
    scr.border(0)

    row_index = []
    for i, (line, j, selected) in enumerate(d):
      if i >= my:
        break
      style = get_style(line)
      if len(line) > mx:
        line = line[:mx] + ">"
      row_index.append(j)
      scr.addstr(i + 1, 1, line + f' <{j}', style)
      if selected:
        scr.addstr(i + 1, 0, "=")

    scr.addstr(0, 4, f"[{diff_path[-20:]}] /{mx} {cur_y}/{my} {row_index[cur_y]}")

    scr.move(cur_y + 1, 1)

    # Draw the screen
    scr.refresh()

    # Wait for a keystroke
    c = scr.getch()
    if c == ord('q'):
      break  # Exit the while loop
    elif c == ord('c'):
      break  # execute cut
    elif c == ord('\t'):
      cur_y -= d.toggle_fold(row_index[cur_y])
    elif c == ord(' '):
      d.toggle_select(row_index[cur_y])
    elif c == curses.KEY_UP:
      if cur_y > 0:
        cur_y -= 1
        scr.move(cur_y + 1, 1)
      elif d.offset > 0:
        d.offset -= 1
    elif c == curses.KEY_DOWN:
      if cur_y < my - 5:
        cur_y += 1
        scr.move(cur_y + 1, 1)
      else:
        d.offset += 1
    elif c == curses.KEY_HOME:
        d.offset = 0
        cur_y = 0
    elif c == curses.KEY_END:
      pass
    elif c == curses.KEY_PPAGE:
      if d.offset >= my:
        d.offset -= my
      else:
        d.offset = 0
        cur_y = 0
    elif c == curses.KEY_NPAGE:
      d.offset += my
    elif c == curses.KEY_LEFT:
      y = d.find_foldable_before(row_index[cur_y])
    elif c == curses.KEY_RIGHT:
      y = d.find_foldable_after(row_index[cur_y])

curses.wrapper(main)
