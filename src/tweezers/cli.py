import argparse
import curses
import subprocess
import sys
from importlib.metadata import version
from tweezers.diff_parser import build_patch, parse_diff
from tweezers.ui import run_ui


def ensure_git_repo():
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0 or result.stdout.strip() != "true":
        print("Not inside a git repository.")
        sys.exit(1)


def get_git_diff():
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Failed to run git diff.")
        sys.exit(1)

    if not result.stdout.strip():
        print("No unstaged changes.")
        sys.exit(0)

    return result.stdout        
    

def apply_patch_to_staging(patch_text):
    """Apply patch to staging area (index). Used for staging working tree changes."""
    result = subprocess.run(
        ["git", "apply", "--cached", "-"],
        input=patch_text.encode(),
    )

    if result.returncode != 0:
        print("Failed to apply patch.")
        sys.exit(1)

    print("Selected changes staged.")
    print("Now run: git commit")


def apply_patch_to_worktree(patch_text):
    """Apply patch to working tree. Used for cherry-picking from commits."""
    result = subprocess.run(
        ["git", "apply", "-"],
        input=patch_text.encode(),
    )

    if result.returncode != 0:
        print("Failed to apply patch.")
        sys.exit(1)

    print("Selected changes applied to working tree.")
    print("Run: git add -p  (to stage selectively)")


def get_commit_diff(commit):
    result = subprocess.run(
        ["git", "show", "--format=", commit],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Invalid commit: {commit}")
        sys.exit(1)

    return result.stdout


def run_git_mode(commit, save_to_files):
    ensure_git_repo()

    if commit is True:
        # --git without param: stage hunks from working tree (like git add -p)
        diff_text = get_git_diff()
        source_info = "git diff"
        apply_to_staging = True
    else:
        # --git <commit>: cherry-pick hunks from a commit to working tree
        diff_text = get_commit_diff(commit)
        source_info = f"git show {commit}"
        apply_to_staging = False

    diff = parse_diff(source_info, diff_text)
    curses.wrapper(run_ui, diff)

    right_patch = build_patch(diff, selected=True)

    if not right_patch.strip():
        print("No hunks selected.")
        return

    if save_to_files:
        with open("right.patch", "w") as f:
            f.write(right_patch)

    if apply_to_staging:
        apply_patch_to_staging(right_patch + '\n')
    else:
        apply_patch_to_worktree(right_patch + '\n')


def run_revert_mode(commit, save_to_files):
    """Revert mode: stage/apply reverted hunks (undo selected changes)."""
    ensure_git_repo()

    if commit is True:
        # --revert without param: revert hunks from working tree to staging
        diff_text = get_git_diff()
        source_info = "git diff (revert)"
        apply_to_staging = True
    else:
        # --revert <commit>: revert hunks from a commit to working tree
        diff_text = get_commit_diff(commit)
        source_info = f"git show {commit} (revert)"
        apply_to_staging = False

    diff = parse_diff(source_info, diff_text)
    curses.wrapper(run_ui, diff)

    # Build a reversed patch for the selected hunks
    reverse_patch = build_patch(diff, selected=True, reverse=True)

    if not reverse_patch.strip():
        print("No hunks selected.")
        return

    if save_to_files:
        with open("revert.patch", "w") as f:
            f.write(reverse_patch)

    if apply_to_staging:
        apply_patch_to_staging(reverse_patch + '\n')
    else:
        apply_patch_to_worktree(reverse_patch + '\n')


def run_file_mode(diff_path):
    with open(diff_path) as f:
        diff_text = f.read()

    diff = parse_diff(diff_path, diff_text)
    curses.wrapper(run_ui, diff)

    with open("left.patch", "w") as f:
        left_patch = build_patch(diff, selected=False)
        f.write(left_patch)

    with open("right.patch", "w") as f:
        right_patch = build_patch(diff, selected=True)
        f.write(right_patch)

    print("Wrote files: left.patch (unselected) and right.patch (selected)")
    

def main():
    parser = argparse.ArgumentParser(
        description="Interactive diff chunk splitter"
    )
    parser.add_argument("diff_file", nargs="?", help="Path to unified diff file")
    parser.add_argument(
        "-o",
        "--output-prefix",
        default="split",
        help="Output prefix (default: split)"
    )
    parser.add_argument("--save", action="store_true",
                    help="Save left.patch and right.patch")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('diff-tweezers')}",
    )
    parser.add_argument("--git", nargs="?", const=True,
                        help="Stage hunks from working tree, or cherry-pick from commit")
    parser.add_argument("--revert", nargs="?", const=True,
                        help="Like --git but stage/apply reverted hunks (undo selected changes)")
    args = parser.parse_args()

    try:
        if args.revert:
            run_revert_mode(args.revert, args.save)
        elif args.git:
            run_git_mode(args.git, args.save)
        else:
            if not args.diff_file:
                print("Missing diff file.")
                sys.exit(1)
            run_file_mode(args.diff_file)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise e
        sys.exit(1)


if __name__ == "__main__":
    main()
