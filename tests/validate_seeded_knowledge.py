"""Validate the committed seed without reading or changing a personal library."""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD", "knowledge-base"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="drama-knowledge-seed-") as temporary:
        destination = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
            for member in source:
                relative = Path(member.name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"Invalid committed seed path: {member.name}")
                if not member.isfile():
                    continue
                stream = source.extractfile(member)
                if stream is None:
                    raise ValueError(f"Unreadable committed seed file: {member.name}")
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(stream.read())
        validator = ROOT / "mm-write-short-drama/scripts/validate_knowledge.py"
        command = [sys.executable, str(validator), "--kb", str(destination / "knowledge-base")]
        subprocess.run([*command, "--fix-index"], cwd=destination, check=True)
        subprocess.run(command, cwd=destination, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
