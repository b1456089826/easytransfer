from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from .scanner_pipeline import scan_frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EasyTransfer scanner (lossy scan simulator)")
    _ = parser.add_argument("--frames", required=True, help="Path to sender frames.jsonl")
    _ = parser.add_argument("--output", required=True, help="Output directory for scanner artifacts")
    _ = parser.add_argument("--loss-rate", type=float, default=0.0, help="Random per-frame loss rate [0,1]")
    _ = parser.add_argument("--burst-rate", type=float, default=0.0, help="Burst loss start probability per frame [0,1]")
    _ = parser.add_argument("--seed", type=int, default=None, help="RNG seed for deterministic simulation")
    args = parser.parse_args(argv)

    frames = cast(str, args.frames)
    output = cast(str, args.output)
    loss_rate = cast(float, args.loss_rate)
    burst_rate = cast(float, args.burst_rate)
    seed = cast(int | None, args.seed)

    result = scan_frames(
        frames_path=frames,
        output_dir=output,
        loss_rate=loss_rate,
        burst_rate=burst_rate,
        seed=seed,
    )

    recommendation_obj = result.feedback.get("recommendation")
    total_need_repair: int | None = None
    if isinstance(recommendation_obj, dict):
        recommendation = cast(dict[str, object], recommendation_obj)
        total_obj = recommendation.get("total_need_repair")
        if isinstance(total_obj, int):
            total_need_repair = total_obj

    summary = {
        "received": str(Path(result.received_path).resolve()),
        "feedback": str(Path(result.feedback_path).resolve()),
        "stats": result.stats,
        "total_need_repair": total_need_repair,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
