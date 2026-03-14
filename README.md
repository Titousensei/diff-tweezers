# Tweezers

Interactive terminal tool for splitting unified diffs by chunk.

![example](/assets/Screenshot_tweezers.png)

## Install

```bash
pip3 install diff-tweezers
```

On Windows, also install:
```bash
pip3 install windows-curses
```

## Usage

### Git Mode (recommended)

**Stage hunks interactively** (like `git add -p`, but better):
```bash
tweezers --git
```
Select hunks to stage, then they're added to the index. Unselected hunks remain in your working tree.

**Cherry-pick hunks from a commit**:
```bash
tweezers --git <commit>
tweezers --git HEAD~3
tweezers --git feature-branch
```
Select hunks to apply to your working tree. Useful for partially applying commits or extracting changes from another branch.

### File Mode

Process a standalone patch file:
```bash
tweezers my.patch
```
Outputs `left.patch` (unselected hunks) and `right.patch` (selected hunks).

### Options

| Option | Description |
|--------|-------------|
| `--git` | Stage hunks from working tree (like `git add -p`) |
| `--git <commit>` | Cherry-pick hunks from a commit to working tree |
| `--save` | Save `right.patch` file in git mode |
| `--version` | Show version |

## Keybindings

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `Space` | Toggle selection |
| `s` | Split chunk at context boundaries |
| `l` / `→` | Unfold |
| `h` / `←` | Fold |
| `]` / `}` | Next file |
| `[` / `{` | Previous file |
| `c` | Confirm and exit |

## License

MIT
