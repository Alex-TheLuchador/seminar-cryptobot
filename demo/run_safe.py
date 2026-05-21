"""
Safe bot demo entry point.

Usage:
    python demo/run_safe.py              # clean headlines, dry-run by default
    python demo/run_safe.py --inject     # injected headline (tripwire should fire)

DRY_RUN=true is the default in .env.example. Set DRY_RUN=false to place real orders.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from safe.agent import run
from safe.config import Config

parser = argparse.ArgumentParser()
parser.add_argument("--inject", action="store_true", help="Use injected headlines payload")
args = parser.parse_args()

headlines = "demo/headlines_injected.json" if args.inject else "demo/headlines_clean.json"
config = Config.load()
run(config, headlines)
