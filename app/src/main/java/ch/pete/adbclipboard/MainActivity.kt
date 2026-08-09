package ch.pete.adbclipboard

import android.app.Activity
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.View.GONE
import android.view.View.VISIBLE
import android.widget.Button

class MainActivity : Activity() {

    private lateinit var prefs: SharedPreferences
    private lateinit var toggleBubbleButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.main_activity)

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)

        findViewById<Button>(R.id.request_permission).setOnClickListener {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivityForResult(intent, REQUEST_OVERLAY_PERMISSION)
        }

        findViewById<Button>(R.id.close_window).setOnClickListener {
            finish()
        }

        findViewById<Button>(R.id.close_app).setOnClickListener {
            val serviceIntent = Intent(this, FloatingViewService::class.java)
            stopService(serviceIntent)
            prefs.edit().putBoolean(PREF_BUBBLE_HIDDEN, true).apply()
            finish()
        }

        toggleBubbleButton = findViewById(R.id.toggle_bubble)
        toggleBubbleButton.setOnClickListener { toggleBubble() }
    }

    override fun onResume() {
        super.onResume()

        val overlayGranted = Settings.canDrawOverlays(this)
        findViewById<Button>(R.id.request_permission).visibility =
            if (overlayGranted) GONE else VISIBLE

        if (overlayGranted && !prefs.getBoolean(PREF_BUBBLE_HIDDEN, false)) {
            startService(Intent(this, FloatingViewService::class.java))
        }
        updateToggleBubbleButton()
    }

    private fun toggleBubble() {
        val hidden = prefs.getBoolean(PREF_BUBBLE_HIDDEN, false)
        if (hidden) {
            prefs.edit().putBoolean(PREF_BUBBLE_HIDDEN, false).apply()
            startService(Intent(this, FloatingViewService::class.java))
        } else {
            stopService(Intent(this, FloatingViewService::class.java))
            prefs.edit().putBoolean(PREF_BUBBLE_HIDDEN, true).apply()
        }
        updateToggleBubbleButton()
    }

    private fun updateToggleBubbleButton() {
        val hidden = prefs.getBoolean(PREF_BUBBLE_HIDDEN, false)
        toggleBubbleButton.text = getString(if (hidden) R.string.show_bubble else R.string.hide_bubble)
    }

    companion object {
        private const val REQUEST_OVERLAY_PERMISSION = 1
        private const val PREFS_NAME = "adb_clipboard_prefs"
        private const val PREF_BUBBLE_HIDDEN = "bubble_hidden"
    }
}
