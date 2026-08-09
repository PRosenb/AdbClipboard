package ch.pete.adbclipboard

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.content.res.Configuration
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.View
import android.view.View.GONE
import android.view.View.VISIBLE
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.slider.Slider
import java.io.File
import java.text.DateFormat
import java.util.Date

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: SharedPreferences

    private lateinit var overlayStatus: TextView
    private lateinit var overlayAction: MaterialButton
    private lateinit var notificationStatus: TextView
    private lateinit var notificationAction: MaterialButton
    private lateinit var bubbleSwitch: MaterialSwitch
    private lateinit var themeToggle: MaterialButton
    private lateinit var bubbleSizeSlider: Slider
    private lateinit var bubbleSizeLabel: TextView
    private lateinit var pcStatusDot: View
    private lateinit var pcStatusText: TextView
    private lateinit var historyList: LinearLayout
    private lateinit var historyEmpty: TextView

    private val refreshHandler = Handler(Looper.getMainLooper())
    private val refreshRunnable = object : Runnable {
        override fun run() {
            refreshStatus()
            refreshHandler.postDelayed(this, REFRESH_INTERVAL_MS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // Apply the persisted theme before the activity is created so there is no
        // flash of the wrong mode (and no redundant recreation). Until the user
        // picks a mode, follow the system.
        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        AppCompatDelegate.setDefaultNightMode(
            when {
                !prefs.contains(PREF_DARK_MODE) -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
                prefs.getBoolean(PREF_DARK_MODE, false) -> AppCompatDelegate.MODE_NIGHT_YES
                else -> AppCompatDelegate.MODE_NIGHT_NO
            }
        )
        super.onCreate(savedInstanceState)
        setContentView(R.layout.main_activity)
        requestNotificationPermissionIfNeeded()

        overlayStatus = findViewById(R.id.overlay_status)
        overlayAction = findViewById(R.id.overlay_action)
        notificationStatus = findViewById(R.id.notification_status)
        notificationAction = findViewById(R.id.notification_action)
        bubbleSwitch = findViewById(R.id.bubble_switch)
        themeToggle = findViewById(R.id.theme_toggle)
        bubbleSizeSlider = findViewById(R.id.bubble_size_slider)
        bubbleSizeLabel = findViewById(R.id.bubble_size_label)
        pcStatusDot = findViewById(R.id.pc_status_dot)
        pcStatusText = findViewById(R.id.pc_status_text)
        historyList = findViewById(R.id.history_list)
        historyEmpty = findViewById(R.id.history_empty)

        overlayAction.setOnClickListener {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivity(intent)
        }

        notificationAction.setOnClickListener {
            requestPermissions(
                arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                REQUEST_NOTIFICATIONS_PERMISSION
            )
        }

        bubbleSwitch.setOnCheckedChangeListener { _, checked -> setBubbleVisible(checked) }

        themeToggle.setOnClickListener {
            val darkMode = isDarkMode()
            prefs.edit().putBoolean(PREF_DARK_MODE, !darkMode).apply()
            AppCompatDelegate.setDefaultNightMode(
                if (darkMode) AppCompatDelegate.MODE_NIGHT_NO else AppCompatDelegate.MODE_NIGHT_YES
            )
        }

        // Bubble size: 36dp (smallest) to 160dp (largest). Persists immediately and
        // live-resizes a running bubble via an intent extra.
        bubbleSizeSlider.valueFrom = FloatingViewService.MIN_BUBBLE_SIZE_DP.toFloat()
        bubbleSizeSlider.valueTo = FloatingViewService.MAX_BUBBLE_SIZE_DP.toFloat()
        bubbleSizeSlider.stepSize = 1f
        bubbleSizeSlider.value =
            prefs.getInt(FloatingViewService.PREF_BUBBLE_SIZE_DP, FloatingViewService.DEFAULT_BUBBLE_SIZE_DP)
                .toFloat()
        bubbleSizeLabel.text = getString(R.string.bubble_size_value, bubbleSizeSlider.value.toInt())
        bubbleSizeSlider.addOnChangeListener { _, value, fromUser ->
            if (!fromUser) return@addOnChangeListener
            val sizeDp = value.toInt()
            bubbleSizeLabel.text = getString(R.string.bubble_size_value, sizeDp)
            prefs.edit().putInt(FloatingViewService.PREF_BUBBLE_SIZE_DP, sizeDp).apply()
            // Only live-resize a bubble that is actually on screen - never start the
            // service just because the size changed (that would resurrect a hidden bubble).
            if (FloatingViewService.isRunning) {
                val intent = Intent(this, FloatingViewService::class.java)
                intent.putExtra(FloatingViewService.EXTRA_BUBBLE_SIZE_DP, sizeDp)
                startService(intent)
            }
        }

        findViewById<MaterialButton>(R.id.exit_button).setOnClickListener { exitApp() }
        findViewById<MaterialButton>(R.id.history_clear).setOnClickListener {
            ClipboardHistory.clear(this)
            renderHistory()
        }

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            findViewById<View>(R.id.notification_row).visibility = GONE
        }
    }

    override fun onResume() {
        super.onResume()
        // Keep the previous behavior: opening the app starts the bubble unless it was
        // deliberately hidden via the switch or Exit app.
        if (Settings.canDrawOverlays(this) &&
            !prefs.getBoolean(PREF_BUBBLE_HIDDEN, false)
        ) {
            startService(Intent(this, FloatingViewService::class.java))
        }
        renderHistory()
        // The bubble can be pinched while this activity is in the back stack, which
        // changes the persisted size - re-sync the slider (programmatic sets fire the
        // change listener with fromUser=false, which the listener ignores).
        bubbleSizeSlider.value =
            prefs.getInt(FloatingViewService.PREF_BUBBLE_SIZE_DP, FloatingViewService.DEFAULT_BUBBLE_SIZE_DP)
                .toFloat()
        bubbleSizeLabel.text = getString(R.string.bubble_size_value, bubbleSizeSlider.value.toInt())
        updateThemeToggle()
        refreshStatus()
        refreshHandler.postDelayed(refreshRunnable, REFRESH_INTERVAL_MS)
    }

    override fun onPause() {
        refreshHandler.removeCallbacks(refreshRunnable)
        super.onPause()
    }

    private fun refreshStatus() {
        // Overlay permission
        val overlayGranted = Settings.canDrawOverlays(this)
        setChip(
            overlayStatus,
            if (overlayGranted) R.string.status_granted else R.string.status_not_granted,
            if (overlayGranted) R.color.chip_green_fg else R.color.chip_red_fg,
            if (overlayGranted) R.color.chip_green_bg else R.color.chip_red_bg
        )
        overlayAction.visibility = if (overlayGranted) GONE else VISIBLE

        // Notification permission (API 33+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val notificationGranted =
                ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
                    PackageManager.PERMISSION_GRANTED
            setChip(
                notificationStatus,
                if (notificationGranted) R.string.status_granted else R.string.status_not_granted,
                if (notificationGranted) R.color.chip_green_fg else R.color.chip_red_fg,
                if (notificationGranted) R.color.chip_green_bg else R.color.chip_red_bg
            )
            notificationAction.visibility = if (notificationGranted) GONE else VISIBLE
        }

        // Floating bubble - only usable when the overlay permission is granted, so the
        // switch is gated on it and a hint explains why it is unavailable.
        val bubbleRunning = FloatingViewService.isRunning && overlayGranted
        bubbleSwitch.setOnCheckedChangeListener(null)
        bubbleSwitch.isEnabled = overlayGranted
        bubbleSwitch.isChecked = bubbleRunning
        bubbleSwitch.setOnCheckedChangeListener { _, checked -> setBubbleVisible(checked) }
        findViewById<View>(R.id.bubble_hint).visibility =
            if (overlayGranted) GONE else VISIBLE

        // PC connection via the heartbeat file the PC script keeps touching
        updatePcStatus()
    }

    private fun isDarkMode(): Boolean {
        return resources.configuration.uiMode and
            Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES
    }

    /** Keeps the header toggle's icon + description in sync with the current mode. */
    private fun updateThemeToggle() {
        val dark = isDarkMode()
        themeToggle.setIconResource(if (dark) R.drawable.ic_light_mode else R.drawable.ic_dark_mode)
        themeToggle.contentDescription = getString(
            if (dark) R.string.theme_toggle_to_light else R.string.theme_toggle_to_dark
        )
    }

    private fun setChip(view: TextView, textRes: Int, fgRes: Int, bgRes: Int) {
        view.text = getString(textRes)
        view.backgroundTintList =
            ColorStateList.valueOf(ContextCompat.getColor(this, bgRes))
        view.setTextColor(ContextCompat.getColor(this, fgRes))
    }

    private fun updatePcStatus() {
        val heartbeat = File(getExternalFilesDir(null), HEARTBEAT_FILE_NAME)
        val ageMs = System.currentTimeMillis() - heartbeat.lastModified()
        val connected = heartbeat.exists() && ageMs < PC_HEARTBEAT_TIMEOUT_MS

        pcStatusDot.backgroundTintList = ColorStateList.valueOf(
            ContextCompat.getColor(
                this,
                if (connected) R.color.status_connected else R.color.status_disconnected
            )
        )
        pcStatusText.text = if (connected) {
            getString(R.string.pc_connected_ago, ageMs / 1000)
        } else {
            getString(R.string.pc_waiting)
        }
    }

    private fun setBubbleVisible(visible: Boolean) {
        val serviceIntent = Intent(this, FloatingViewService::class.java)
        if (visible) {
            prefs.edit().putBoolean(PREF_BUBBLE_HIDDEN, false).apply()
            startService(serviceIntent)
        } else {
            stopService(serviceIntent)
            prefs.edit().putBoolean(PREF_BUBBLE_HIDDEN, true).apply()
            BubbleNotifications.showBubbleHiddenNotification(this)
        }
        refreshStatus()
    }

    private fun exitApp() {
        stopService(Intent(this, FloatingViewService::class.java))
        prefs.edit().putBoolean(PREF_BUBBLE_HIDDEN, true).apply()
        BubbleNotifications.showBubbleHiddenNotification(this)
        finish()
    }

    private fun renderHistory() {
        historyList.removeAllViews()
        val entries = ClipboardHistory.load(this)
        historyEmpty.visibility = if (entries.isEmpty()) VISIBLE else GONE

        val dateFormat = DateFormat.getTimeInstance(DateFormat.SHORT)
        entries.forEach { entry ->
            val row = layoutInflater.inflate(R.layout.history_item, historyList, false)
            row.findViewById<TextView>(R.id.history_preview).text = entry.text
            row.findViewById<TextView>(R.id.history_time).text =
                dateFormat.format(Date(entry.timestamp))
            row.findViewById<MaterialButton>(R.id.history_copy).setOnClickListener {
                copyToClipboard(entry.text)
            }
            row.findViewById<MaterialButton>(R.id.history_delete).setOnClickListener {
                ClipboardHistory.remove(this, entry.timestamp)
                renderHistory()
            }
            historyList.addView(row)
        }
    }

    private fun copyToClipboard(text: String) {
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText(text, text))
        Toast.makeText(this, R.string.copied_to_clipboard, Toast.LENGTH_SHORT).show()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED &&
            !prefs.getBoolean(PREF_NOTIF_PERMISSION_REQUESTED, false)
        ) {
            prefs.edit().putBoolean(PREF_NOTIF_PERMISSION_REQUESTED, true).apply()
            requestPermissions(
                arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                REQUEST_NOTIFICATIONS_PERMISSION
            )
        }
    }

    companion object {
        private const val REQUEST_NOTIFICATIONS_PERMISSION = 2
        private const val PREFS_NAME = "adb_clipboard_prefs"
        private const val PREF_BUBBLE_HIDDEN = "bubble_hidden"
        private const val PREF_DARK_MODE = "dark_mode"
        private const val PREF_NOTIF_PERMISSION_REQUESTED = "notif_permission_requested"
        private const val HEARTBEAT_FILE_NAME = "heartbeat"
        private const val PC_HEARTBEAT_TIMEOUT_MS = 20_000L
        private const val REFRESH_INTERVAL_MS = 3000L
    }
}
