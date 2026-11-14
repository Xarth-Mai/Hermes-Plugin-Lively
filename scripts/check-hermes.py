"""Run the offline, pinned-host contract harness (kept with integration tests)."""

from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/hermes_contract.py"), run_name="__main__")
