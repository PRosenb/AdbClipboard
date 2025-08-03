package ch.pete.adbclipboard

import android.app.Activity
import android.content.ClipboardManager
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import timber.log.Timber
import java.io.File
import java.io.FileWriter
import java.io.IOException

class ClipboardReaderActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.clipboard_reader_activity)
        handleReadClipboardRequest()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        handleReadClipboardRequest()
    }

    private fun handleReadClipboardRequest() {
        Handler(Looper.getMainLooper()).postDelayed(
            { readClipboard() },
            CLIPBOARD_READ_DELAY_MS
        )
    }

    private fun readClipboard() {
        Timber.d(TAG, "Attempting to read clipboard...")

        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        val text: String
        if (clipboard.hasPrimaryClip()) {
            val clip = clipboard.primaryClip
            val item = clip?.getItemAt(0)
            text = if (item?.text != null) item.text.toString() else ""
            Timber.d(TAG, "Read clipboard: $text")
        } else {
            text = ""
            Timber.e(TAG, "Clipboard is empty or inaccessible")
        }

        // Write to file for ADB access
        try {
            val file = File(getExternalFilesDir(null), CLIPBOARD_CONTENT_FILE_NAME)
            val writer = FileWriter(file)
            writer.write(text)
            writer.close()
            Timber.d(TAG, "Wrote clipboard to: " + file.absolutePath)
        } catch (e: IOException) {
            Timber.e(TAG, "Failed to write to file: " + e.message)
        }

        this.finish()
    }

    companion object {
        private const val TAG = "AdbClipboard"

        /**
         * We need to wait a bit for the system to give us access to the clipboard
         */
        private const val CLIPBOARD_READ_DELAY_MS = 1000L
        private const val CLIPBOARD_CONTENT_FILE_NAME = "clipboard.txt"
    }
}
