"""Canonical manifest models (deterministic JSON)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import cast

from .utils import JSONValue, ensure_json_object, sha256_hex, stable_json_dumps_bytes, utc_now_iso


MANIFEST_VERSION = 1


def _require_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{field} must be an integer")
        return int(value)
    raise ValueError(f"{field} must be an integer")


@dataclass(frozen=True, slots=True)
class ManifestFileEntry:
    """One file record in a transfer manifest."""

    path: str
    size: int
    sha256: str
    meta: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        if self.size < 0:
            raise ValueError("size must be >= 0")
        return {
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256,
            "meta": dict(self.meta),
        }

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "ManifestFileEntry":
        path = str(d["path"])
        size = _require_int(d["size"], field="size")
        sha256 = str(d["sha256"])
        meta = ensure_json_object(d.get("meta", {}))
        return ManifestFileEntry(path=path, size=size, sha256=sha256, meta=meta)


@dataclass(frozen=True, slots=True)
class TransferManifest:
    """Transfer manifest serialized with stable_json_dumps_bytes."""

    transfer_id: str
    created_utc: str = field(default_factory=utc_now_iso)
    version: int = MANIFEST_VERSION
    files: list[ManifestFileEntry] = field(default_factory=list)

    chunk_size: int = 256 * 1024
    framing: dict[str, JSONValue] = field(default_factory=lambda: {"name": "etp", "version": 1})

    compression: dict[str, JSONValue] = field(default_factory=lambda: {"policy": "auto"})
    fec: dict[str, JSONValue] = field(default_factory=lambda: {"scheme": "xor", "group_size": 4})

    meta: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        if self.version != MANIFEST_VERSION:
            raise ValueError(f"Unsupported manifest version: {self.version}")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        return {
            "version": self.version,
            "transfer_id": self.transfer_id,
            "created_utc": self.created_utc,
            "chunk_size": self.chunk_size,
            "framing": dict(self.framing),
            "compression": dict(self.compression),
            "fec": dict(self.fec),
            "files": [f.to_dict() for f in self.files],
            "meta": dict(self.meta),
        }

    def to_canonical_json_bytes(self) -> bytes:
        return stable_json_dumps_bytes(self.to_dict())

    def canonical_sha256(self) -> str:
        return sha256_hex(self.to_canonical_json_bytes())

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "TransferManifest":
        version = _require_int(d.get("version", 0), field="version")
        if version != MANIFEST_VERSION:
            raise ValueError(f"Unsupported manifest version: {version}")
        files_raw_obj = d.get("files", [])
        if not isinstance(files_raw_obj, list):
            raise ValueError("files must be a list")
        files: list[ManifestFileEntry] = []
        for item in cast(list[object], files_raw_obj):
            if not isinstance(item, dict):
                raise ValueError("file entry must be an object")
            files.append(ManifestFileEntry.from_dict(cast(Mapping[str, object], item)))

        chunk_size = _require_int(d.get("chunk_size", 256 * 1024), field="chunk_size")
        return TransferManifest(
            transfer_id=str(d["transfer_id"]),
            created_utc=str(d.get("created_utc", utc_now_iso())),
            version=version,
            files=files,
            chunk_size=chunk_size,
            framing=ensure_json_object(d.get("framing", {"name": "etp", "version": 1})),
            compression=ensure_json_object(d.get("compression", {"policy": "auto"})),
            fec=ensure_json_object(d.get("fec", {"scheme": "xor", "group_size": 4})),
            meta=ensure_json_object(d.get("meta", {})),
        )

    @staticmethod
    def from_canonical_json_bytes(data: bytes) -> "TransferManifest":
        from typing import cast as _cast

        obj = _cast(object, json.loads(data.decode("utf-8")))
        return TransferManifest.from_dict(ensure_json_object(obj))
