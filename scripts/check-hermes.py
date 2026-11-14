"""Offline pinned Hermes contract runner; delegates to the separate integration test."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/hermes_contract.py"), run_name="__main__")
