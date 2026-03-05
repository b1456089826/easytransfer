from __future__ import annotations

import argparse
import sys

from .sender_pipeline import run_sender_pipeline


class _SenderArgs(argparse.Namespace):
    input: str = ""
    output: str = ""
    block_size: int = 64 * 1024
    symbol_size: int = 1024
    redundancy: float = 0.0
    fps: float = 30.0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="easytransfer-sender")
    _ = p.add_argument(
        "--input",
        required=True,
        help="Input file or directory to package",
    )
    _ = p.add_argument(
        "--output",
        required=True,
        help="Output directory for manifest and frames",
    )
    _ = p.add_argument(
        "--block-size",
        type=int,
        default=64 * 1024,
        help="Block size in bytes (default: 65536)",
    )
    _ = p.add_argument(
        "--symbol-size",
        type=int,
        default=1024,
        help="Symbol size in bytes (default: 1024)",
    )
    _ = p.add_argument(
        "--redundancy",
        type=float,
        default=0.0,
        help="Redundant symbol ratio per block, e.g. 0.2 for +20%% (default: 0)",
    )
    _ = p.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Frames-per-second metadata for playback/scanning (default: 30)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv, namespace=_SenderArgs())
    manifest_path, frames_path = run_sender_pipeline(
        input_path=args.input,
        output_dir=args.output,
        block_size=args.block_size,
        symbol_size=args.symbol_size,
        redundancy=args.redundancy,
        fps=args.fps,
    )
    _ = sys.stdout.write(f"\nWrote:\n- {manifest_path}\n- {frames_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
