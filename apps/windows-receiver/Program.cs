using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace EasyTransferReceiver;

internal static class Program
{
    private sealed record SourceSpec(string SymbolId, string File, int Size);
    private sealed record FileSpec(string Path, int Size, string Sha256, string Compression, List<string> SourceSymbolIds);

    private static int Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.WriteLine("Usage: EasyTransferReceiver <received.jsonl> <manifest.json> <outputDir>");
            return 2;
        }

        var inputPath = Path.GetFullPath(args[0]);
        var manifestPath = Path.GetFullPath(args[1]);
        var outputDir = Path.GetFullPath(args[2]);

        try
        {
            Directory.CreateDirectory(outputDir);

            var symbolMap = LoadReceivedSymbols(inputPath);
            var (files, sourceMap) = LoadManifest(manifestPath);

            var report = new Dictionary<string, object?>
            {
                ["ok"] = true,
                ["files_written"] = new List<string>(),
                ["files_failed"] = new List<string>(),
                ["missing_source_symbols"] = new List<string>(),
                ["errors"] = new List<string>()
            };

            foreach (var file in files)
            {
                try
                {
                    var chunks = new List<byte[]>();
                    foreach (var sid in file.SourceSymbolIds)
                    {
                        if (!symbolMap.TryGetValue(sid, out var bytes))
                        {
                            ((List<string>)report["missing_source_symbols"]!).Add(sid);
                            throw new InvalidOperationException($"Missing symbol: {sid}");
                        }
                        chunks.Add(bytes);
                    }

                    var compressed = Concat(chunks);
                    var raw = Decompress(file.Compression, compressed);

                    if (raw.Length != file.Size)
                        throw new InvalidOperationException($"Size mismatch for {file.Path}");

                    var hash = Sha256Hex(raw);
                    if (!string.Equals(hash, file.Sha256, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidOperationException($"SHA mismatch for {file.Path}");

                    var outPath = SafeJoin(outputDir, file.Path);
                    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
                    File.WriteAllBytes(outPath, raw);
                    ((List<string>)report["files_written"]!).Add(file.Path);
                }
                catch (Exception e)
                {
                    ((List<string>)report["files_failed"]!).Add(file.Path);
                    ((List<string>)report["errors"]!).Add(e.Message);
                    report["ok"] = false;
                }
            }

            var reportPath = Path.Combine(outputDir, "receiver_report.json");
            File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
            Console.WriteLine($"Wrote report: {reportPath}");
            Console.WriteLine($"OK={report["ok"]}");
            return (bool)report["ok"]! ? 0 : 1;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 3;
        }
    }

    private static (List<FileSpec> Files, Dictionary<string, SourceSpec> Sources) LoadManifest(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;

        var files = new List<FileSpec>();
        foreach (var f in root.GetProperty("files").EnumerateArray())
        {
            var sourceIds = f.GetProperty("source_symbol_ids").EnumerateArray().Select(x => x.GetString()!).ToList();
            files.Add(new FileSpec(
                f.GetProperty("path").GetString()!,
                f.GetProperty("size").GetInt32(),
                f.GetProperty("sha256").GetString()!,
                f.GetProperty("compression").GetString() ?? "none",
                sourceIds
            ));
        }

        var sources = new Dictionary<string, SourceSpec>();
        if (root.TryGetProperty("sources", out var srcArray))
        {
            foreach (var s in srcArray.EnumerateArray())
            {
                var sid = s.GetProperty("symbol_id").GetString()!;
                sources[sid] = new SourceSpec(sid, s.GetProperty("file").GetString()!, s.GetProperty("size").GetInt32());
            }
        }

        return (files, sources);
    }

    private static Dictionary<string, byte[]> LoadReceivedSymbols(string path)
    {
        var map = new Dictionary<string, byte[]>();
        foreach (var line in File.ReadLines(path))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            var sid = root.GetProperty("symbol_id").GetString();
            var b64 = root.GetProperty("data_b64").GetString();
            if (string.IsNullOrWhiteSpace(sid) || string.IsNullOrWhiteSpace(b64)) continue;
            map[sid] = Convert.FromBase64String(b64);
        }
        return map;
    }

    private static byte[] Decompress(string codec, byte[] data)
    {
        return codec.ToLowerInvariant() switch
        {
            "none" => data,
            "zlib" => DecompressZlib(data),
            "gzip" => DecompressGzip(data),
            "deflate" => DecompressDeflate(data),
            _ => data,
        };
    }

    private static byte[] DecompressZlib(byte[] data)
    {
        using var input = new MemoryStream(data);
        using var ds = new System.IO.Compression.ZLibStream(input, System.IO.Compression.CompressionMode.Decompress);
        using var output = new MemoryStream();
        ds.CopyTo(output);
        return output.ToArray();
    }

    private static byte[] DecompressGzip(byte[] data)
    {
        using var input = new MemoryStream(data);
        using var ds = new System.IO.Compression.GZipStream(input, System.IO.Compression.CompressionMode.Decompress);
        using var output = new MemoryStream();
        ds.CopyTo(output);
        return output.ToArray();
    }

    private static byte[] DecompressDeflate(byte[] data)
    {
        using var input = new MemoryStream(data);
        using var ds = new System.IO.Compression.DeflateStream(input, System.IO.Compression.CompressionMode.Decompress);
        using var output = new MemoryStream();
        ds.CopyTo(output);
        return output.ToArray();
    }

    private static byte[] Concat(List<byte[]> chunks)
    {
        var total = chunks.Sum(x => x.Length);
        var output = new byte[total];
        var offset = 0;
        foreach (var chunk in chunks)
        {
            Buffer.BlockCopy(chunk, 0, output, offset, chunk.Length);
            offset += chunk.Length;
        }
        return output;
    }

    private static string Sha256Hex(byte[] data)
    {
        var hash = SHA256.HashData(data);
        var sb = new StringBuilder(hash.Length * 2);
        foreach (var b in hash) sb.Append(b.ToString("x2"));
        return sb.ToString();
    }

    private static string SafeJoin(string root, string relative)
    {
        if (Path.IsPathRooted(relative) || relative.Contains(".."))
            throw new InvalidOperationException("Unsafe output path");
        var full = Path.GetFullPath(Path.Combine(root, relative));
        if (!full.StartsWith(Path.GetFullPath(root), StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Unsafe output path");
        return full;
    }
}
