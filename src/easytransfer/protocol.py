"""Frame encoding/decoding and XOR parity helpers."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
import json
from collections.abc import Iterator, Mapping, Sequence
from typing import cast

from .utils import JSONValue, ensure_json_object, crc32_u32, pad_right, stable_json_dumps_bytes, xor_many


MAGIC = b"ETP1"
VERSION = 1

_HDR_STRUCT = struct.Struct(">4sBBBBIII")
_CRC_STRUCT = struct.Struct(">I")
_META_LEN_STRUCT = struct.Struct(">H")


class NeedMoreData(Exception):
    pass


class FrameType(IntEnum):
    MANIFEST = 1
    DATA = 2
    PARITY = 3


@dataclass(frozen=True, slots=True)
class Frame:
    """One binary frame (header + payload + CRC)."""

    frame_type: FrameType
    flags: int
    stream_id: int
    seq: int
    payload: bytes


def encode_frame(frame: Frame) -> bytes:
    if not (0 <= frame.flags <= 255):
        raise ValueError("flags out of range")
    if not (0 <= frame.stream_id <= 0xFFFFFFFF):
        raise ValueError("stream_id out of range")
    if not (0 <= frame.seq <= 0xFFFFFFFF):
        raise ValueError("seq out of range")
    if len(frame.payload) > 0xFFFFFFFF:
        raise ValueError("payload too large")
    header = _HDR_STRUCT.pack(
        MAGIC,
        VERSION,
        int(frame.frame_type),
        frame.flags,
        0,
        frame.stream_id,
        frame.seq,
        len(frame.payload),
    )
    crc = crc32_u32(header + frame.payload)
    return header + frame.payload + _CRC_STRUCT.pack(crc)


def decode_frame(buf: bytes, *, max_payload_bytes: int = 8 * 1024 * 1024) -> tuple[Frame, bytes]:
    if len(buf) < _HDR_STRUCT.size:
        raise NeedMoreData
    unpacked = cast(tuple[bytes, int, int, int, int, int, int, int], _HDR_STRUCT.unpack_from(buf, 0))
    magic, ver, ftype, flags, _rsv, stream_id, seq, payload_len = unpacked
    if magic != MAGIC:
        raise ValueError("bad magic")
    if ver != VERSION:
        raise ValueError("unsupported version")
    if payload_len > max_payload_bytes:
        raise ValueError("payload exceeds max_payload_bytes")
    need = _HDR_STRUCT.size + payload_len + _CRC_STRUCT.size
    if len(buf) < need:
        raise NeedMoreData
    payload = buf[_HDR_STRUCT.size : _HDR_STRUCT.size + payload_len]
    crc_offset = _HDR_STRUCT.size + int(payload_len)
    expected_crc = cast(tuple[int], _CRC_STRUCT.unpack_from(buf, crc_offset))[0]
    actual_crc = crc32_u32(buf[: _HDR_STRUCT.size] + payload)
    if expected_crc != actual_crc:
        raise ValueError("frame crc mismatch")
    frame = Frame(
        frame_type=FrameType(int(ftype)),
        flags=int(flags),
        stream_id=int(stream_id),
        seq=int(seq),
        payload=payload,
    )
    rest = buf[need:]
    return frame, rest


def iter_decode_frames(data: bytes, *, max_payload_bytes: int = 8 * 1024 * 1024) -> Iterator[Frame]:
    buf = data
    while buf:
        frame, buf = decode_frame(buf, max_payload_bytes=max_payload_bytes)
        yield frame


def encode_enveloped_payload(meta: Mapping[str, JSONValue], data: bytes) -> bytes:
    meta_bytes = stable_json_dumps_bytes(dict(meta))
    if len(meta_bytes) > 0xFFFF:
        raise ValueError("meta too large")
    return _META_LEN_STRUCT.pack(len(meta_bytes)) + meta_bytes + data


def decode_enveloped_payload(payload: bytes) -> tuple[dict[str, JSONValue], bytes]:
    if len(payload) < _META_LEN_STRUCT.size:
        raise ValueError("payload too short")
    meta_len = cast(tuple[int], _META_LEN_STRUCT.unpack_from(payload, 0))[0]
    start = _META_LEN_STRUCT.size
    end = start + meta_len
    if len(payload) < end:
        raise ValueError("payload too short")
    meta_obj = cast(object, json.loads(payload[start:end].decode("utf-8")))
    return ensure_json_object(meta_obj), payload[end:]


def xor_parity(chunks: Sequence[bytes]) -> tuple[bytes, tuple[int, ...]]:
    if not chunks:
        raise ValueError("chunks must be non-empty")
    sizes = tuple(len(c) for c in chunks)
    max_len = max(sizes)
    padded = [pad_right(c, max_len) for c in chunks]
    return xor_many(padded), sizes


def xor_recover_one(chunks: Sequence[bytes | None], *, parity: bytes, sizes: Sequence[int]) -> bytes:
    if len(chunks) != len(sizes):
        raise ValueError("chunks and sizes length mismatch")
    missing = [i for i, c in enumerate(chunks) if c is None]
    if len(missing) != 1:
        raise ValueError("exactly one chunk must be missing")
    max_len = max(sizes) if sizes else len(parity)
    if len(parity) != max_len:
        raise ValueError("parity length mismatch")
    present: list[bytes] = []
    for i, c in enumerate(chunks):
        if c is None:
            continue
        if len(c) != sizes[i]:
            raise ValueError("chunk length does not match sizes")
        present.append(pad_right(c, max_len))
    recovered_padded = xor_many([parity, *present])
    miss_idx = missing[0]
    return recovered_padded[: sizes[miss_idx]]
