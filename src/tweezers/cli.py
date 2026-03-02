import argparse
import curses
import subprocess
import sys
from diff_parser import build_patch, parse_diff
from ui import run_ui


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
    

def apply_selected_patch(patch_text):
    result = subprocess.run(
        ["git", "apply", "--cached", "-"],
        input=patch_text.encode(),
    )

    if result.returncode != 0:
        print("Failed to apply patch.")
        sys.exit(1)

    print("Selected changes staged.")
    print("Now run: git commit")


def run_git_mode():
    ensure_git_repo()

    diff_text = get_git_diff()
    diff = parse_diff("git diff", diff_text)
    curses.wrapper(run_ui, diff)

    right_patch = build_patch(diff, selected=True)

    if not right_patch.strip():
        print("No hunks selected.")
        return

    apply_selected_patch(right_patch + '\n')


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
    parser.add_argument(
        "--version",
        action="version",
        version="tweezers 0.2.0"
    )
    parser.add_argument("--git", action="store_true")
    args = parser.parse_args()

    try:
        if args.git:
            run_git_mode()
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
