import argparse
import curses
import sys
from ui import run_ui


def main():
    parser = argparse.ArgumentParser(
        description="Interactive diff chunk splitter"
    )
    parser.add_argument("diff", help="Path to unified diff file")
    parser.add_argument(
        "-o",
        "--output-prefix",
        default="split",
        help="Output prefix (default: split)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="tweezers 0.1.0"
    )

    args = parser.parse_args()

    try:
        curses.wrapper(run_ui, args.diff, args.output_prefix)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
