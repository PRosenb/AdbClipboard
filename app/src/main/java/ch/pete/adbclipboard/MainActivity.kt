package ch.pete.adbclipboard

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import timber.log.Timber

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

        findViewById<Button>(R.id.close_window).setOnClickListener {
            finish()
        }

        findViewById<Button>(R.id.close_app).setOnClickListener {
            val serviceIntent = Intent(this, FloatingViewService::class.java)
            stopService(serviceIntent)
            finish()
        }
    }

    companion object {
        private const val REQUEST_OVERLAY_PERMISSION = 1
    }
}
