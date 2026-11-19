"""Stable measured-code entry name; use benchmark.py for preparation/analysis."""
import sys
from benchmark import main
if __name__ == '__main__': main(['run', *sys.argv[1:]])
