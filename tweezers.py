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
      ret = "> " + ret
      try:
        pos = self.chunks.index(i)
        self.i = self.chunks[pos + 1]
      except:
        pass

    return ret

  def toggle_fold(self, i):
    i = i + self.offset - 1
    l = self.lines[i]
    while not (l.startswith('diff ') or l.startswith('@@ ')):
      i -= 1
      l = self.lines[i]
    if i in self._folded:
      self._folded.remove(i)
    else:
      self._folded.add(i)
    return i - self.offset + 1

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
  if l.startswith('diff ') or l.startswith('> diff '):
    return curses.A_BOLD # COLOR_WHITE
  elif l.startswith('--- '):
    return curses.A_BOLD | curses.color_pair(1) # COLOR_RED
  elif l.startswith('+++ '):
    return curses.A_BOLD | curses.color_pair(2) # COLOR_GREEN
  elif l.startswith('@@ ') or l.startswith('> @@ '):
    return curses.A_BOLD | curses.color_pair(4) # COLOR_BLUE
  elif l.startswith('-'):
    return curses.color_pair(1) # COLOR_RED
  elif l.startswith('+'):
    return curses.color_pair(2) # COLOR_GREEN
  elif l.startswith('>diff '):
    return curses.A_DIM # COLOR_WHITE
  elif l.startswith('>@@ '):
    return curses.color_pair(4) # COLOR_BLUE
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

  y = 1
  while True:
    # First, clear the screen
    scr.erase()
    my, mx = scr.getmaxyx()

    # print on screen here
    scr.border(0)
    scr.addstr(0, 4, f"[{diff_path[-20:]}] /{mx} {y}/{my}")

    for i, line in enumerate(d, 1):
      if i > my - 2:
        break
      style = get_style(line)
      if len(line) > mx - 2:
        line = line[:mx - 2] + ">"
      scr.addstr(i, 1, line, style)

    scr.move(y,1)

    # Draw the screen
    scr.refresh()

    # Wait for a keystroke
    c = scr.getch()
    if c == ord('q'):
      break  # Exit the while loop
    elif c == ord('c'):
      break  # execute cut
    elif c == ord(' '):
      pass
    elif c == curses.KEY_UP:
      if y > 1:
        y -= 1
        scr.move(y,1)
      else:
        d.offset -= 1
    elif c == curses.KEY_DOWN:
      if y < my - 5:
        y += 1
        scr.move(y,1)
      else:
        d.offset += 1
    elif c == curses.KEY_HOME:
      pass
    elif c == curses.KEY_END:
      pass
    elif c == curses.KEY_PPAGE:
      if d.offset >= my:
        d.offset -= my
      else:
        d.offset = 0
        y = 1
    elif c == curses.KEY_NPAGE:
      d.offset += my
    elif c == curses.KEY_LEFT or c == curses.KEY_RIGHT:
      y = d.toggle_fold(y)

curses.wrapper(main)
