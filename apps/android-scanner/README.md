# EasyTransfer Android Scanner

## Build

```bash
cd apps/android-scanner
./gradlew assembleDebug
```

## Function

- CameraX continuous scanning + frame decoding
- Parse single control frame metadata and show progress
- Deduplicate symbols by `symbol_id` and detect conflicts
- Validate missing shards, upload `manifest` + symbols to Windows
- Persist Windows address and uploaded symbol resume state

Export directory is app external files under `scan-validate-upload/`.
