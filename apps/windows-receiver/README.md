# EasyTransfer Windows Receiver

## Build

```bash
cd apps/windows-receiver
dotnet build -c Release
```

## Run

```bash
dotnet run -- \
  ../../out/e2e-demo/scan/received.jsonl \
  ../../out/e2e-demo/send/manifest.json \
  ../../out/windows-recv
```

Program verifies hash/size and writes `receiver_report.json`.
