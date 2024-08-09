#! /usr/bin/env python3

from collections import namedtuple
import curses
import sys

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
    file = None
    chunk = None
    lines = []
    ret = FoldingDiff(path)
    with open(path) as f:
        for i, line in enumerate(f):
            line = line.strip()
            try:
                if line.startswith(PREFIX_DIFF):
                    ret._add_file(line)
                elif line.startswith(PREFIX_PLUS) or line.startswith(PREFIX_MINUS):
                    ret._add_label(line)
                elif line.startswith(PREFIX_CHUNK):
                    ret._add_chunk(line)
                else:
                    ret._add_line(line)
            except Exception as ex:
                print("ERROR -", ex, "at line", i, line)
                raise
    return ret



diff_obj = parse_diff(sys.argv[1])
print(diff_obj)
