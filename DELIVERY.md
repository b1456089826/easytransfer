# EasyTransfer Three-End Delivery

## Delivered Components

1. **Browser Sender Extension**
   - Path: `apps/extension-sender`
   - Package: `packaging/deliverables/extension-sender.zip`
   - Features: file selection, size-based compression choice for small files, symbol+repair frame generation, frame playback canvas.

2. **Android Scanner App (source package)**
   - Path: `apps/android-scanner`
   - Package: `packaging/deliverables/android-scanner-source.zip`
   - Features: CameraX preview, ZXing decode, symbol deduplication, `received.jsonl` + `feedback.json` export.

3. **Windows Receiver App (source package)**
   - Path: `apps/windows-receiver`
   - Package: `packaging/deliverables/windows-receiver-source.zip`
   - Features: read scanner JSONL + manifest, decompress/reconstruct files, hash verification, receiver report output.

4. **Core Protocol/Tooling Package**
   - Python dist: `dist/easytransfer-0.1.0-py3-none-any.whl`, `dist/easytransfer-0.1.0.tar.gz`

## Verification Results

- Python unit/integration tests: PASS (`3 passed`)
- End-to-end pipeline demo: PASS (`out/e2e-demo` generated with sender/scan/recv artifacts)
- Compression policy check from manifest:
  - `small.txt` (<1MiB) -> `bz2` (best-ratio path)
  - `medium.txt` -> `zlib`
  - `blob.bin` -> `none`

## Environment Constraints Encountered

- `dotnet` not available in current environment, so Windows binary compilation was not executable here.
- Android local build toolchain missing (`gradle` command not present), so APK build was not executable here.

Source projects and packaging scripts are provided for build on proper Windows/Android build hosts.
