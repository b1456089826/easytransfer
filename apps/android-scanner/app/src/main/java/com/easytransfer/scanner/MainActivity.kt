package com.easytransfer.scanner

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Base64
import android.widget.Button
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.zxing.BinaryBitmap
import com.google.zxing.MultiFormatReader
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.PlanarYUVLuminanceSource
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var statusText: TextView
    private lateinit var exportButton: Button

    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private val decoder = MultiFormatReader()
    private val session = mutableListOf<String>()
    private val seenIds = hashSetOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        previewView = findViewById(R.id.previewView)
        statusText = findViewById(R.id.statusText)
        exportButton = findViewById(R.id.exportButton)

        exportButton.setOnClickListener {
            exportSession()
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), 1001)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1001 && grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            statusText.text = "Camera permission denied"
        }
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()

            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }

            val analyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also {
                    it.setAnalyzer(cameraExecutor, FrameAnalyzer { payload ->
                        processPayload(payload)
                    })
                }

            val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(this, cameraSelector, preview, analyzer)
        }, ContextCompat.getMainExecutor(this))
    }

    private fun processPayload(payload: String) {
        runOnUiThread {
            try {
                val obj = JSONObject(payload)
                val symbolId = obj.optString("symbol_id")
                if (symbolId.isNotBlank() && !seenIds.contains(symbolId)) {
                    seenIds.add(symbolId)
                    val out = JSONObject()
                    out.put("symbol_id", symbolId)
                    out.put("data_b64", obj.optString("payload_b64"))
                    out.put("file_id", obj.optInt("fileId", -1))
                    out.put("block", obj.optInt("block", -1))
                    out.put("symbol", obj.optInt("symbol", -1))
                    out.put("redundant", obj.optBoolean("redundant", false))
                    session.add(out.toString())
                    statusText.text = "Captured: ${seenIds.size} symbols"
                }
            } catch (_: Exception) {
            }
        }
    }

    private fun exportSession() {
        try {
            val outDir = File(getExternalFilesDir(null), "session")
            outDir.mkdirs()
            val received = File(outDir, "received.jsonl")
            received.writeText(session.joinToString("\n", postfix = if (session.isEmpty()) "" else "\n"))

            val feedback = File(outDir, "feedback.json")
            val fb = JSONObject()
            fb.put("captured", seenIds.size)
            fb.put("recommendation", JSONObject().put("note", "Use receiver to detect missing symbols and request补传"))
            feedback.writeText(fb.toString(2))

            statusText.text = "Exported to: ${outDir.absolutePath}"
        } catch (e: Exception) {
            statusText.text = "Export failed: ${e.message}"
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
                    false
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
