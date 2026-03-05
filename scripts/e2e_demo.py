#!/usr/bin/env python3
"""Run an end-to-end EasyTransfer demo pipeline."""

from __future__ import annotations

import argparse
import os
import random
import shutil
import string
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], env: dict[str, str]) -> None:
    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def _make_input(input_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "small.txt").write_text(
        "\n".join(["easytransfer demo line"] * 5000),
        encoding="utf-8",
    )

    medium_payload = "".join(random.choices(string.ascii_letters + string.digits, k=2 * 1024 * 1024))
    (input_dir / "medium.txt").write_text(medium_payload, encoding="utf-8")

    (input_dir / "blob.bin").write_bytes(os.urandom(128 * 1024))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EasyTransfer e2e demo")
    parser.add_argument("--workdir", required=True, help="Working directory for generated artifacts")
    parser.add_argument("--loss-rate", type=float, default=0.0, help="Scanner random loss rate [0,1]")
    parser.add_argument("--burst-rate", type=float, default=0.0, help="Scanner burst loss rate [0,1]")
    parser.add_argument("--seed", type=int, default=42, help="Scanner RNG seed")
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    input_dir = workdir / "input"
    send_dir = workdir / "send"
    scan_dir = workdir / "scan"
    recv_dir = workdir / "recv"

    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    _make_input(input_dir)

    env = dict(os.environ)
    src_dir = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(src_dir) + os.pathsep + env.get("PYTHONPATH", "")

    _run(
        [
            sys.executable,
            "-m",
            "easytransfer.sender_cli",
            "--input",
            str(input_dir),
            "--output",
            str(send_dir),
            "--block-size",
            str(2 * 1024 * 1024),
            "--symbol-size",
            "1024",
            "--redundancy",
            "0.2",
            "--fps",
            "30",
        ],
        env,
    )

    _run(
        [
            sys.executable,
            "-m",
            "easytransfer.scanner_cli",
            "--frames",
            str(send_dir / "frames.jsonl"),
            "--output",
            str(scan_dir),
            "--loss-rate",
            str(args.loss_rate),
            "--burst-rate",
            str(args.burst_rate),
            "--seed",
            str(args.seed),
        ],
        env,
    )

    _run(
        [
            sys.executable,
            "-m",
            "easytransfer.receiver_cli",
            "--input",
            str(scan_dir / "received.jsonl"),
            "--manifest",
            str(send_dir / "manifest.json"),
            "--output",
            str(recv_dir),
        ],
        env,
    )

    print(f"Demo finished. Artifacts in: {workdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
