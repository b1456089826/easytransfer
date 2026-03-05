"""Small stdlib-only utilities used by the protocol core."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import zlib
from collections.abc import Iterator, Sequence
from typing import TypeAlias, cast


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crc32_u32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def stable_json_dumps(obj: object) -> str:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def stable_json_dumps_bytes(obj: object) -> bytes:
    return stable_json_dumps(obj).encode("utf-8")


def iter_chunks(data: bytes, chunk_size: int) -> Iterator[bytes]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def xor_bytes(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("xor_bytes requires equal-length inputs")
    return bytes(x ^ y for x, y in zip(a, b))


def xor_many(chunks: Sequence[bytes]) -> bytes:
    if not chunks:
        raise ValueError("chunks must be non-empty")
    n = len(chunks[0])
    if any(len(c) != n for c in chunks):
        raise ValueError("all chunks must have equal length")
    out = bytearray(n)
    for c in chunks:
        for i, v in enumerate(c):
            out[i] ^= v
    return bytes(out)


def pad_right(data: bytes, size: int, pad_byte: int = 0) -> bytes:
    if size < 0:
        raise ValueError("size must be >= 0")
    if len(data) > size:
        raise ValueError("data longer than size")
    if len(data) == size:
        return data
    return data + bytes([pad_byte]) * (size - len(data))


def ensure_json_object(obj: object) -> dict[str, JSONValue]:
    if not isinstance(obj, dict):
        raise ValueError("expected JSON object")
    obj = cast(dict[object, object], obj)
    out: dict[str, JSONValue] = {}
    for k, v in obj.items():
        if not isinstance(k, str):
            raise ValueError("JSON object keys must be strings")
        out[k] = _ensure_json_value(v)
    return out


def _ensure_json_value(v: object) -> JSONValue:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, list):
        return [_ensure_json_value(x) for x in cast(list[object], v)]
    if isinstance(v, dict):
        return ensure_json_object(cast(dict[object, object], v))
    raise ValueError("value is not JSON-serializable")
