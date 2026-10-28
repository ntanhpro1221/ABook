"""Fresh, task-local fixture/evidence for the same guarded hidden 120 s gate."""
from pathlib import Path
import hidden_suite

hidden_suite.EVIDENCE = Path(__file__).resolve().parents[1] / "build/idlecpu-evidence/hidden"

if __name__ == "__main__":
    hidden_suite.main()
