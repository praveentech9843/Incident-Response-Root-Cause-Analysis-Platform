"""
Root wrapper for Phase 5 E2E Verification.
Delegates to backend/verify_phase5_e2e.py.
"""
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    script_path = Path(__file__).resolve().parent / "backend" / "verify_phase5_e2e.py"
    res = subprocess.run([sys.executable, str(script_path)], cwd=script_path.parent)
    sys.exit(res.returncode)
