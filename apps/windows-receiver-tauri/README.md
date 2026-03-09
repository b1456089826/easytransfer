# EasyTransfer Windows Receiver (Tauri)

## Local Build

```bash
cd apps/windows-receiver-tauri
npm install
npm run tauri:build
```

## Runtime

Fill these in UI:

- `received.jsonl`
- output folder

`manifest.auto.json` is uploaded by Android automatically and saved next to `received.jsonl`.

Click **Reconstruct** to restore files and generate `receiver_report.json`.
