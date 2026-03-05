from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

from .compression_layer import CompressionEnvelope, DecompressionLimits, build_default_registry, decompress_bytes
from .utils import JSONValue, ensure_json_object, sha256_hex, xor_many


class ReceiverError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class FileSpec:
    path: str
    size: int
    sha256: str
    compression: str
    compression_params: dict[str, JSONValue]
    source_symbol_ids: tuple[str, ...]


@dataclasses.dataclass
class ReceiverReport:
    ok: bool
    files_written: list[str]
    files_failed: list[str]
    recovered_source_symbols: list[str]
    missing_source_symbols: list[str]
    missing_repair_symbols: list[str]
    verified_source_symbols: int
    verified_repair_symbols: int
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "files_written": self.files_written,
            "files_failed": self.files_failed,
            "recovered_source_symbols": self.recovered_source_symbols,
            "missing_source_symbols": self.missing_source_symbols,
            "missing_repair_symbols": self.missing_repair_symbols,
            "verified_source_symbols": self.verified_source_symbols,
            "verified_repair_symbols": self.verified_repair_symbols,
            "errors": self.errors,
        }


def load_manifest(
    manifest_path: str | os.PathLike[str],
) -> tuple[list[FileSpec], dict[str, dict[str, object]], list[dict[str, object]]]:
    p = Path(manifest_path)
    if not p.exists():
        raise ReceiverError(f"Manifest not found: {manifest_path}")
    try:
        loaded = cast(object, json.loads(p.read_text(encoding="utf-8")) )
    except json.JSONDecodeError as e:
        raise ReceiverError(f"Invalid manifest JSON: {e}") from e
    if not isinstance(loaded, dict):
        raise ReceiverError("Manifest must be a JSON object")
    raw = cast(dict[str, object], loaded)

    files: list[FileSpec] = []
    files_obj = raw.get("files")
    if not isinstance(files_obj, list):
        files_obj = []
    for obj_raw in cast(list[object], files_obj):
        if not isinstance(obj_raw, dict):
            continue
        obj = cast(dict[str, object], obj_raw)
        sid_list_obj = obj.get("source_symbol_ids")
        if not isinstance(sid_list_obj, list):
            continue
        sid_list: list[str] = []
        bad_sid = False
        for sid_item in cast(list[object], sid_list_obj):
            if not isinstance(sid_item, str):
                bad_sid = True
                break
            sid_list.append(sid_item)
        if bad_sid:
            continue
        path = obj.get("path")
        size = obj.get("size")
        sha = obj.get("sha256")
        compression = obj.get("compression")
        params_obj = obj.get("compression_params", {})
        if not isinstance(path, str) or not isinstance(size, int) or not isinstance(sha, str):
            continue
        if not isinstance(compression, str):
            compression = "none"
        if not isinstance(params_obj, dict):
            params_obj = {}
        try:
            params = ensure_json_object(cast(dict[object, object], params_obj))
        except ValueError:
            params = {}
        files.append(
            FileSpec(
                path=path,
                size=size,
                sha256=sha,
                compression=compression,
                compression_params=params,
                source_symbol_ids=tuple(sid_list),
            )
        )

    sources: dict[str, dict[str, object]] = {}
    sources_raw = raw.get("sources")
    if isinstance(sources_raw, list):
        for s_raw in cast(list[object], sources_raw):
            if not isinstance(s_raw, dict):
                continue
            s = cast(dict[str, object], s_raw)
            sid = s.get("symbol_id")
            if isinstance(sid, str):
                sources[sid] = s

    repairs: list[dict[str, object]] = []
    repairs_raw = raw.get("repairs")
    if isinstance(repairs_raw, list):
        for r_raw in cast(list[object], repairs_raw):
            if not isinstance(r_raw, dict):
                continue
            repairs.append(cast(dict[str, object], r_raw))

    return files, sources, repairs


def load_scanner_artifact(input_path: str | os.PathLike[str]) -> dict[str, bytes]:
    p = Path(input_path)
    if not p.exists():
        raise ReceiverError(f"Scanner artifact not found: {input_path}")
    out: dict[str, bytes] = {}

    sources: list[Path]
    if p.is_dir():
        candidates = sorted(x for x in p.iterdir() if x.is_file() and x.suffix.lower() in {".jsonl", ".ndjson"})
        preferred = [x for x in candidates if x.name == "received.jsonl"]
        sources = preferred + [x for x in candidates if x not in preferred]
    else:
        sources = [p]

    for src in sources:
        records = _read_jsonl(src)
        for rec in records:
            sid_obj = rec.get("symbol_id")
            if not isinstance(sid_obj, str):
                continue
            payload_obj = rec.get("data_b64")
            if not isinstance(payload_obj, str):
                payload_obj = rec.get("payload_b64") if isinstance(rec.get("payload_b64"), str) else None
            if not isinstance(payload_obj, str):
                continue
            if sid_obj in out:
                continue
            try:
                data = base64.b64decode(payload_obj, validate=False)
            except Exception as e:
                raise ReceiverError(f"Invalid base64 for symbol {sid_obj}: {e}") from e
            out[sid_obj] = data

    return out


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = cast(object, json.loads(s))
            except json.JSONDecodeError as e:
                raise ReceiverError(f"Invalid JSONL at {path}:{line_no}: {e}") from e
            if isinstance(obj, dict):
                records.append(cast(dict[str, object], obj))
    return records


def _attempt_xor_recovery(
    have: dict[str, bytes],
    repairs: list[dict[str, object]],
    source_specs: dict[str, dict[str, object]],
    *,
    errors: list[str],
) -> list[str]:
    recovered: list[str] = []
    progressed = True
    while progressed:
        progressed = False
        for rep in repairs:
            rid = rep.get("symbol_id")
            xor_of = rep.get("xor_of")
            if not isinstance(rid, str) or not isinstance(xor_of, list):
                continue
            if rid not in have:
                continue
            source_ids: list[str] = []
            for x in cast(list[object], xor_of):
                if isinstance(x, str):
                    source_ids.append(x)
            missing = [sid for sid in source_ids if sid not in have]
            if len(missing) != 1:
                continue
            known = [sid for sid in source_ids if sid in have]
            try:
                max_len = max([len(have[rid])] + [len(have[sid]) for sid in known])
            except ValueError:
                continue
            rep_payload = _pad(have[rid], max_len)
            known_payloads = [_pad(have[sid], max_len) for sid in known]
            rec = xor_many([rep_payload, *known_payloads])
            target = missing[0]
            spec = source_specs.get(target, {})
            target_len = spec.get("size")
            if isinstance(target_len, int) and target_len >= 0:
                rec = rec[:target_len]
            try:
                _validate_symbol_payload(symbol_id=target, payload=rec, spec=spec)
            except ReceiverError as e:
                errors.append(str(e))
                continue
            have[target] = rec
            recovered.append(target)
            progressed = True
    return recovered


def _pad(data: bytes, n: int) -> bytes:
    if len(data) >= n:
        return data
    return data + (b"\x00" * (n - len(data)))


def _safe_join(base_dir: Path, rel_path: str) -> Path:
    rel = Path(rel_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ReceiverError(f"Unsafe output path: {rel_path}")
    out = (base_dir / rel).resolve()
    base = base_dir.resolve()
    if not str(out).startswith(str(base) + os.sep) and out != base:
        raise ReceiverError(f"Unsafe output path: {rel_path}")
    return out


def _validate_symbol_payload(*, symbol_id: str, payload: bytes, spec: Mapping[str, object]) -> None:
    size = spec.get("size")
    if isinstance(size, int) and size >= 0 and len(payload) != size:
        raise ReceiverError(f"Symbol size mismatch for {symbol_id}: got={len(payload)} expected={size}")
    sha = spec.get("sha256")
    if isinstance(sha, str):
        got = hashlib.sha256(payload).hexdigest()
        if got != sha:
            raise ReceiverError(f"Symbol sha256 mismatch for {symbol_id}: got={got} expected={sha}")


def _repair_specs_index(repairs: Iterable[dict[str, object]]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for rep in repairs:
        rid = rep.get("symbol_id")
        if isinstance(rid, str):
            out[rid] = rep
    return out


def run_receiver(input_path: str, manifest_path: str, output_dir: str) -> ReceiverReport:
    files, source_specs, repairs = load_manifest(manifest_path)
    have = load_scanner_artifact(input_path)
    repair_specs = _repair_specs_index(repairs)

    errors: list[str] = []
    verified_source_symbols = 0
    verified_repair_symbols = 0

    for sid, payload in list(have.items()):
        if sid in source_specs:
            try:
                _validate_symbol_payload(symbol_id=sid, payload=payload, spec=source_specs[sid])
                verified_source_symbols += 1
            except ReceiverError as e:
                errors.append(str(e))
                _ = have.pop(sid, None)
        elif sid in repair_specs:
            try:
                _validate_symbol_payload(symbol_id=sid, payload=payload, spec=repair_specs[sid])
                verified_repair_symbols += 1
            except ReceiverError as e:
                errors.append(str(e))
                _ = have.pop(sid, None)

    recovered_source = _attempt_xor_recovery(have, repairs, source_specs, errors=errors)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files_written: list[str] = []
    files_failed: list[str] = []

    registry = build_default_registry()
    limits = DecompressionLimits(
        max_output_bytes=512 * 1024 * 1024,
        max_input_bytes=512 * 1024 * 1024,
        max_ratio=5000.0,
    )

    for f in files:
        try:
            chunks: list[bytes] = []
            for sid in f.source_symbol_ids:
                if sid not in have:
                    raise ReceiverError(f"Missing source symbol {sid} for file {f.path}")
                chunks.append(have[sid])
            compressed = b"".join(chunks)
            env = CompressionEnvelope(
                codec=f.compression,
                original_size=f.size,
                compressed_size=len(compressed),
                params=f.compression_params,
            )
            raw = decompress_bytes(env, compressed, registry=registry, limits=limits)
            got = sha256_hex(raw)
            if got != f.sha256:
                raise ReceiverError(f"SHA256 mismatch for {f.path}: got={got} expected={f.sha256}")

            out_path = _safe_join(out_dir, f.path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            _ = out_path.write_bytes(raw)
            files_written.append(f.path)
        except Exception as e:
            files_failed.append(f.path)
            errors.append(str(e))

    missing_source = sorted([sid for sid in source_specs.keys() if sid not in have])
    missing_repair = sorted([sid for sid in repair_specs.keys() if sid not in have])
    report = ReceiverReport(
        ok=(len(files_failed) == 0 and len(missing_source) == 0),
        files_written=sorted(files_written),
        files_failed=sorted(set(files_failed)),
        recovered_source_symbols=sorted(set(recovered_source)),
        missing_source_symbols=missing_source,
        missing_repair_symbols=missing_repair,
        verified_source_symbols=verified_source_symbols,
        verified_repair_symbols=verified_repair_symbols,
        errors=errors,
    )
    _ = (Path(output_dir) / "receiver_report.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
