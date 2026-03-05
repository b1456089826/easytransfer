from __future__ import annotations

import unittest

from easytransfer.compression_layer import CompressionPolicy, build_default_registry, compress_bytes


class CompressionPolicyTests(unittest.TestCase):
    def test_small_file_auto_picks_best_available_ratio(self) -> None:
        data = (b"A" * 1024) * 200
        reg = build_default_registry()

        env_auto, payload_auto = compress_bytes(data, registry=reg, policy=CompressionPolicy.AUTO)

        compressed_sizes = {}
        for name in reg.available():
            codec = reg.get(name)
            payload, _params = codec.compress(data, policy=CompressionPolicy.BEST_RATIO)
            compressed_sizes[name] = len(payload)

        min_size = min(compressed_sizes.values())
        self.assertEqual(env_auto.compressed_size, min_size)
        self.assertEqual(len(payload_auto), min_size)


if __name__ == "__main__":
    unittest.main()
