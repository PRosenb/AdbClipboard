package ch.pete.adbclipboard

import android.app.Activity
import android.content.ClipboardManager
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import timber.log.Timber
import java.io.File
import java.io.FileWriter
import java.io.IOException

class ClipboardReaderActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.clipboard_reader_activity)

        handleRequest()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        handleRequest()
    }

    private fun handleRequest() {
        Handler(Looper.getMainLooper()).postDelayed(
            { readClipboard() },
            CLIPBOARD_READ_DELAY_MS
        )
    }

    private fun readClipboard() {
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
        } else {
            Timber.e(TAG, "Clipboard is empty or inaccessible")
            Toast.makeText(this, "Clipboard is empty", Toast.LENGTH_LONG).show()
            val resultIntent = Intent("ch.pete.adbclipboard.RESULT")
            resultIntent.putExtra("text", "")
            sendBroadcast(resultIntent)
        }

        this.finish()
    }

    companion object {
        private const val CLIPBOARD_READ_DELAY_MS = 1000L
        private const val TAG = "AdbClipboard"
    }
}
