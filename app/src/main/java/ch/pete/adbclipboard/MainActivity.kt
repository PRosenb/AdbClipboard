package ch.pete.adbclipboard

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.View.GONE
import android.view.View.VISIBLE
import android.widget.Button

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.main_activity)

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
            finish()
        }
    }

    override fun onResume() {
        super.onResume()

        if (Settings.canDrawOverlays(this)) {
            findViewById<Button>(R.id.request_permission).visibility = GONE

            val intent = Intent(this, FloatingViewService::class.java)
            startForegroundService(intent) // Use foreground service for better reliability
        } else {
            findViewById<Button>(R.id.request_permission).visibility = VISIBLE
        }
    }

    companion object {
        private const val REQUEST_OVERLAY_PERMISSION = 1
    }
}
