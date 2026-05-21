"""
Entry point for the unsafe bot demo. Runs one decision cycle and exits.

Usage:
    python demo/run_unsafe.py             # uses headlines_clean.json
    python demo/run_unsafe.py --inject    # uses headlines_injected.json (prompt injection demo)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unsafe.bot import run_once


def main():
    inject = "--inject" in sys.argv
    headlines_path = "demo/headlines_injected.json" if inject else "demo/headlines_clean.json"
    label = "INJECTED" if inject else "CLEAN"

    print(f"Unsafe bot -- one decision cycle -- headlines: {label}")
    print(f"Source: {headlines_path}")
    print("=" * 70)
    run_once(headlines_path=headlines_path)


if __name__ == "__main__":
    main()
