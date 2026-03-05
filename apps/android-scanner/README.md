# EasyTransfer Android Scanner

## Build

```bash
cd apps/android-scanner
./gradlew assembleDebug
```

## Function

- CameraX preview + frame analysis
- ZXing decode for frame payload JSON
- Deduplicate symbols by `symbol_id`
- Export `received.jsonl` and `feedback.json` for receiver side

Export directory is app external files under `session/`.
