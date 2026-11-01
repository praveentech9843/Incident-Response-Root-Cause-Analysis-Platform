"""
Root wrapper for Phase 6 E2E Verification.
Runs backend/verify_phase6_e2e.py using backend virtual environment.
"""
import sys
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).parent.resolve()
    backend_dir = root_dir / "backend"
    venv_python = backend_dir / ".venv" / "Scripts" / "python.exe"

    if not venv_python.exists():
        # Fallback to standard python in PATH
        venv_python = "python"

    script_path = backend_dir / "verify_phase6_e2e.py"

    print(f"Launching Phase 6 E2E Verification via {venv_python}...\n")
    result = subprocess.run([str(venv_python), str(script_path)], cwd=str(root_dir))
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
