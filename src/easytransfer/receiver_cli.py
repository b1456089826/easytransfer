from __future__ import annotations

import argparse
import json
import sys
from typing import cast

from .receiver_pipeline import ReceiverError, run_receiver


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="easytransfer-receiver")
    _ = p.add_argument("--input", required=True, help="Scanner artifact JSONL path")
    _ = p.add_argument("--manifest", required=True, help="Sender manifest.json path")
    _ = p.add_argument("--output", required=True, help="Output directory for reconstructed files")
    _ = p.add_argument("--json", action="store_true", help="Print full report JSON")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_path = cast(str, args.input)
    manifest_path = cast(str, args.manifest)
    output_dir = cast(str, args.output)
    print_json = cast(bool, args.json)
    try:
        report = run_receiver(input_path, manifest_path, output_dir)
    except ReceiverError as e:
        _ = sys.stderr.write(f"receiver error: {e}\n")
        return 2
    except Exception as e:
        _ = sys.stderr.write(f"unexpected error: {e}\n")
        return 3

    if print_json:
        _ = sys.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    else:
        _ = sys.stdout.write(
            "\n".join(
                [
                    f"ok: {report.ok}",
                    f"files_written: {len(report.files_written)}",
                    f"files_failed: {len(report.files_failed)}",
                    f"missing_source_symbols: {len(report.missing_source_symbols)}",
                    f"missing_repair_symbols: {len(report.missing_repair_symbols)}",
                    f"recovered_source_symbols: {len(report.recovered_source_symbols)}",
                    f"report_path: {output_dir.rstrip('/')}/receiver_report.json",
                ]
            )
            + "\n"
        )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
