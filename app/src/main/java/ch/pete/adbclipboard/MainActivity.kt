package ch.pete.adbclipboard

import android.app.Activity
import android.content.ClipboardManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Toast
import timber.log.Timber
import java.io.File
import java.io.FileWriter
import java.io.IOException

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Timber.plant(Timber.DebugTree())
        setContentView(R.layout.main_activity)

        // Check if permission is granted
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (!Settings.canDrawOverlays(this)) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivityForResult(intent, REQUEST_OVERLAY_PERMISSION)
            }
            if (Settings.canDrawOverlays(this)) {
                val intent = Intent(this, FloatingViewService::class.java)
                startForegroundService(intent) // Use foreground service for better reliability
            }
        } else {
            // TODO lower versions?
        }

        handleRequest(false)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        handleRequest(true)
    }

    private fun handleRequest(finish: Boolean) {
        Handler(Looper.getMainLooper()).postDelayed(
            { readClipboard(finish) },
            CLIPBOARD_READ_DELAY_MS
        )
    }

    private fun readClipboard(finish: Boolean) {
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        Timber.d(TAG, "Attempting to read clipboard...")
        if (clipboard.hasPrimaryClip()) {
            val clip = clipboard.primaryClip
            val item = clip!!.getItemAt(0)
            val text = if (item.text != null) item.text.toString() else "null"
            Timber.d(TAG, "Read clipboard: $text")
            println("Read clipboard: $text")
            Toast.makeText(this, "Clipboard: $text", Toast.LENGTH_LONG).show()

            // Write to file for ADB access
            try {
                val file = File(getExternalFilesDir(null), "clipboard.txt")
                val writer = FileWriter(file)
                writer.write(text)
                writer.close()
                Timber.d(TAG, "Wrote clipboard to: " + file.absolutePath)
            } catch (e: IOException) {
                Timber.e(TAG, "Failed to write to file: " + e.message)
            }

            // Broadcast result for ADB
            val resultIntent = Intent("ch.pete.adbclipboard.RESULT")
            resultIntent.putExtra("text", text)
            sendBroadcast(resultIntent)
        } else {
            Timber.e(TAG, "Clipboard is empty or inaccessible")
            Toast.makeText(this, "Clipboard is empty", Toast.LENGTH_LONG).show()
            val resultIntent = Intent("ch.pete.adbclipboard.RESULT")
            resultIntent.putExtra("text", "")
            sendBroadcast(resultIntent)
        }

        if (finish) {
            this.finish()
        }
    }

    companion object {
        private const val CLIPBOARD_READ_DELAY_MS = 1000L
        private const val TAG = "AdbClipboard"
        private const val REQUEST_OVERLAY_PERMISSION = 1
    }
}
