package ch.pete.adbclipboard

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.os.Bundle
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

        handleRequest(intent)
    }

    private fun handleRequest(intent: Intent) {
        val action = intent.action
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager

        if (ACTION_WRITE == action) {
            val text = intent.getStringExtra("text")
            if (text != null) {
                val clip = ClipData.newPlainText("AdbClipboard", text)
                clipboard.setPrimaryClip(clip)
                Timber.d(TAG, "Set clipboard to: $text")
                Toast.makeText(this, "Clipboard set to: $text", Toast.LENGTH_SHORT).show()
            } else {
                Timber.e(TAG, "No text provided in intent")
                Toast.makeText(this, "Error: No text provided", Toast.LENGTH_SHORT).show()
            }
        } else if (ACTION_READ == action) {
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
        } else {
            Timber.e(TAG, "Unknown action: $action")
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        intent?.let {
            handleRequest(it)
        }
    }

    companion object {
        private const val TAG = "AdbClipboard"
        private const val ACTION_WRITE = "ch.pete.adbclipboard.WRITE"
        private const val ACTION_READ = "ch.pete.adbclipboard.READ"
    }
}
