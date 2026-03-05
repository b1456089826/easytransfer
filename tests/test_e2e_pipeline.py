from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from easytransfer.receiver_pipeline import run_receiver
from easytransfer.scanner_pipeline import scan_frames
from easytransfer.sender_pipeline import run_sender_pipeline


class EndToEndPipelineTests(unittest.TestCase):
    def test_sender_scanner_receiver_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "input"
            send_dir = root / "send"
            scan_dir = root / "scan"
            recv_dir = root / "recv"
            input_dir.mkdir(parents=True, exist_ok=True)

            (input_dir / "a.txt").write_text("hello" * 2000, encoding="utf-8")
            (input_dir / "b.bin").write_bytes(b"x" * 50000)

            manifest_path, frames_path = run_sender_pipeline(
                input_path=str(input_dir),
                output_dir=str(send_dir),
                block_size=32768,
                symbol_size=1024,
                redundancy=0.25,
                fps=30.0,
            )
            scan_frames(
                frames_path=str(frames_path),
                output_dir=str(scan_dir),
                loss_rate=0.0,
                burst_rate=0.0,
                seed=1,
            )
            report = run_receiver(
                input_path=str(scan_dir / "received.jsonl"),
                manifest_path=str(manifest_path),
                output_dir=str(recv_dir),
            )

            self.assertTrue(report.ok)
            self.assertEqual(sorted(report.files_failed), [])
            self.assertEqual(
                (recv_dir / "a.txt").read_text(encoding="utf-8"),
                (input_dir / "a.txt").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (recv_dir / "b.bin").read_bytes(),
                (input_dir / "b.bin").read_bytes(),
            )

    def test_receiver_recovers_one_missing_source_symbol_with_repair(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "input"
            send_dir = root / "send"
            scan_dir = root / "scan"
            recv_dir = root / "recv"
            input_dir.mkdir(parents=True, exist_ok=True)

            data = ("recover-me-" * 1200).encode("utf-8")
            (input_dir / "recover.txt").write_bytes(data)

            manifest_path, frames_path = run_sender_pipeline(
                input_path=str(input_dir),
                output_dir=str(send_dir),
                block_size=65536,
                symbol_size=1024,
                redundancy=0.5,
                fps=30.0,
            )

            frames = []
            with frames_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    frames.append(json.loads(line))

            target_source_symbol = None
            for rec in frames:
                if rec.get("kind") == "symbol" and rec.get("redundant") is False:
                    target_source_symbol = rec.get("symbol_id")
                    break
            self.assertIsNotNone(target_source_symbol)

            scan_dir.mkdir(parents=True, exist_ok=True)
            received_path = scan_dir / "received.jsonl"
            with received_path.open("w", encoding="utf-8") as out:
                for rec in frames:
                    if rec.get("kind") != "symbol":
                        continue
                    if rec.get("symbol_id") == target_source_symbol:
                        continue
                    out_rec = {
                        "symbol_id": rec.get("symbol_id"),
                        "data_b64": rec.get("payload_b64"),
                        "path": rec.get("path"),
                        "file_id": rec.get("file_id"),
                        "block": rec.get("block"),
                        "symbol": rec.get("symbol"),
                        "redundant": rec.get("redundant"),
                    }
                    out.write(json.dumps(out_rec, ensure_ascii=False) + "\n")

            report = run_receiver(
                input_path=str(received_path),
                manifest_path=str(manifest_path),
                output_dir=str(recv_dir),
            )

            self.assertTrue(report.ok)
            self.assertIn(target_source_symbol, report.recovered_source_symbols)
            self.assertEqual(
                (recv_dir / "recover.txt").read_bytes(),
                (input_dir / "recover.txt").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
