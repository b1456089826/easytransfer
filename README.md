# EasyTransfer MVP

Offline frame-stream file transfer proof-of-concept:

- Sender CLI: package files, compress, symbol/frame encode.
- Scanner CLI: simulate lossy scan and produce feedback.
- Receiver CLI: reconstruct files and verify integrity.

## Quick start

```bash
python3 -m pip install -e .
python3 scripts/e2e_demo.py --workdir /tmp/easytransfer-demo
```

## CLIs

```bash
easytransfer-sender --input ./sample_data --output ./out/send
easytransfer-scanner --frames ./out/send/frames.jsonl --output ./out/scan
easytransfer-receiver --input ./out/scan/received.jsonl --manifest ./out/send/manifest.json --output ./out/recv
```

## Compression policy

- `<= 1 MiB`: choose best ratio among available codecs.
- `1 MiB ~ 32 MiB`: balanced compression default.
- `> 32 MiB`: fast compression default.
