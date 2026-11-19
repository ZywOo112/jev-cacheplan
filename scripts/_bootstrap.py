"""Make repository scripts usable from any working directory; installed SOLO is external."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
