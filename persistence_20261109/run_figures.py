"""Recreate the six figures from the submission's processed plotting inputs."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
for number in range(1, 7):
    subprocess.run([sys.executable, str(root / "figures" / f"figure{number}.py")], cwd=root, check=True)

