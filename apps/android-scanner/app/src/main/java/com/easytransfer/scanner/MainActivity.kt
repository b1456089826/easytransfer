package com.easytransfer.scanner

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.zxing.BinaryBitmap
import com.google.zxing.MultiFormatReader
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import org.json.JSONObject
import java.io.File
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {

    private lateinit var windowsAddrInput: EditText
    private lateinit var previewView: PreviewView
    private lateinit var statusText: TextView
    private lateinit var startScanButton: Button
    private lateinit var stopScanButton: Button
    private lateinit var exportButton: Button

    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private val uploadExecutor = Executors.newSingleThreadExecutor()
    private val session = mutableListOf<String>()
    private val seenIds = hashSetOf<String>()
    private var scannedCount = 0
    private var uploadedCount = 0
    private var isScanning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        windowsAddrInput = findViewById(R.id.windowsAddrInput)
        previewView = findViewById(R.id.previewView)
        statusText = findViewById(R.id.statusText)
        startScanButton = findViewById(R.id.startScanButton)
        stopScanButton = findViewById(R.id.stopScanButton)
        exportButton = findViewById(R.id.exportButton)

        startScanButton.setOnClickListener { startScan() }
        stopScanButton.setOnClickListener { stopScan() }
        exportButton.setOnClickListener { exportSession() }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdownNow()
        uploadExecutor.shutdownNow()
    }

    private fun startScan() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), 1001)
            return
        }
        if (isScanning) {
            statusText.text = "正在扫码中"
            return
        }
        isScanning = true
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
            val analyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also {
                    it.setAnalyzer(cameraExecutor, FrameAnalyzer { payload ->
                        onPayloadDecoded(payload)
                    })
                }
            provider.unbindAll()
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analyzer)
            statusText.text = "已开始扫码，等待码帧..."
        }, ContextCompat.getMainExecutor(this))
    }

    private fun stopScan() {
        isScanning = false
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            providerFuture.get().unbindAll()
            statusText.text = "已停止扫码"
        }, ContextCompat.getMainExecutor(this))
    }

    private fun onPayloadDecoded(payload: String) {
        if (!isScanning) return
        try {
            val obj = JSONObject(payload)
            if (obj.optString("kind") != "symbol") {
                return
            }
            val symbolId = obj.optString("symbol_id")
            if (symbolId.isBlank() || seenIds.contains(symbolId)) {
                return
            }
            seenIds.add(symbolId)
            scannedCount += 1

            val windowsAddr = windowsAddrInput.text?.toString()?.trim().orEmpty()
            if (windowsAddr.isBlank()) {
                runOnUiThread { statusText.text = "请先填写 Windows 地址" }
                return
            }

            val uploadObj = JSONObject()
            uploadObj.put("symbol_id", symbolId)
            uploadObj.put("data_b64", obj.optString("payload_b64"))
            uploadObj.put("file_id", obj.optInt("fileId", -1))
            uploadObj.put("block", obj.optInt("block", -1))
            uploadObj.put("symbol", obj.optInt("symbol", -1))
            uploadObj.put("redundant", obj.optBoolean("redundant", false))

            uploadExecutor.execute {
                val ok = uploadToWindows(windowsAddr, uploadObj.toString())
                runOnUiThread {
                    if (ok) {
                        uploadedCount += 1
                        session.add(uploadObj.toString())
                        statusText.text = "扫码 $scannedCount，已上传 $uploadedCount"
                    } else {
                        statusText.text = "上传失败，等待下一帧"
                    }
                }
            }
        } catch (_: Exception) {
        }
    }

    private fun uploadToWindows(addr: String, payload: String): Boolean {
        return try {
            val endpoint = if (addr.startsWith("http://") || addr.startsWith("https://")) {
                "$addr/upload-symbol"
            } else {
                "http://$addr/upload-symbol"
            }
            val url = URL(endpoint)
            val conn = (url.openConnection() as HttpURLConnection)
            conn.requestMethod = "POST"
            conn.connectTimeout = 3000
            conn.readTimeout = 5000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            val bytes = payload.toByteArray(Charsets.UTF_8)
            conn.setRequestProperty("Content-Length", bytes.size.toString())
            conn.outputStream.use { out: OutputStream -> out.write(bytes) }
            val code = conn.responseCode
            code in 200..299
        } catch (_: Exception) {
            false
        }
    }

    private fun exportSession() {
        try {
            val outDir = File(getExternalFilesDir(null), "scan-upload-session")
            outDir.mkdirs()
            val jsonl = File(outDir, "uploaded_symbols.jsonl")
            jsonl.writeText(session.joinToString("\n", postfix = if (session.isEmpty()) "" else "\n"))

            val report = JSONObject()
            report.put("scanned", scannedCount)
            report.put("uploaded", uploadedCount)
            report.put("note", "Android 已扫码并上传至 Windows")
            File(outDir, "upload_report.json").writeText(report.toString(2))

            statusText.text = "已导出：${outDir.absolutePath}"
        } catch (e: Exception) {
            statusText.text = "导出失败：${e.message}"
        }
    }
}

private class FrameAnalyzer(
    private val onPayload: (String) -> Unit,
) : ImageAnalysis.Analyzer {
    private val reader = MultiFormatReader()

    override fun analyze(image: ImageProxy) {
        val mediaImage = image.image
        if (mediaImage != null) {
            try {
                val plane = image.planes[0]
                val data = plane.buffer.toByteArray()
                val source = PlanarYUVLuminanceSource(
                    data,
                    image.width,
                    image.height,
                    0,
                    0,
                    image.width,
                    image.height,
                    false,
                )
                val bitmap = BinaryBitmap(HybridBinarizer(source))
                val result = reader.decodeWithState(bitmap)
                onPayload(result.text)
            } catch (_: Exception) {
            } finally {
                reader.reset()
            }
        }
        image.close()
    }
}

private fun ByteBuffer.toByteArray(): ByteArray {
    rewind()
    val data = ByteArray(remaining())
    get(data)
    return data
}
