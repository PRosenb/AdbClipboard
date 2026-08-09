package ch.pete.adbclipboard

import android.annotation.SuppressLint
import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.os.IBinder
import android.view.GestureDetector
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager

class FloatingViewService : Service() {

    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private lateinit var gestureDetector: GestureDetector
    private var isDragging = false
    private var longPressed = false

    override fun onBind(intent: Intent?): IBinder? = null

    @SuppressLint("InflateParams")
    override fun onCreate() {
        super.onCreate()

        floatingView = LayoutInflater.from(this).inflate(R.layout.floating_widget, null)

        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onLongPress(e: MotionEvent) {
                // Long-press hides the bubble (non-persistent; the app can bring it back)
                longPressed = true
                stopSelf()
            }
        })

        // Single action source, also keeps the bubble clickable for accessibility
        floatingView.setOnClickListener {
            if (!isDragging && !longPressed) {
                startClipboardReaderActivity()
            }
        }

        // Set up window parameters
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        )
        params.gravity = Gravity.TOP or Gravity.START
        params.x = 0
        params.y = 100

        // Add view to window manager
        windowManager = getSystemService(WindowManager::class.java)
        windowManager.addView(floatingView, params)

        makeDraggable(floatingView, params)
    }

    private fun makeDraggable(
        view: View,
        params: WindowManager.LayoutParams
    ) {
        val dragThreshold = ViewConfiguration.get(this).scaledTouchSlop

        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f

        view.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    isDragging = false
                    longPressed = false
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    gestureDetector.onTouchEvent(event)
                    true
                }

                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - initialTouchX
                    val dy = event.rawY - initialTouchY
                    if (!isDragging &&
                        (Math.abs(dx) > dragThreshold || Math.abs(dy) > dragThreshold)) {
                        isDragging = true
                    }
                    if (isDragging) {
                        params.x = initialX + dx.toInt()
                        params.y = initialY + dy.toInt()
                        windowManager.updateViewLayout(view, params)
                    }
                    gestureDetector.onTouchEvent(event)
                    true
                }

                MotionEvent.ACTION_UP -> {
                    gestureDetector.onTouchEvent(event)
                    view.performClick()
                    true
                }

                else -> {
                    gestureDetector.onTouchEvent(event)
                    true
                }
            }
        }
    }

    private fun startClipboardReaderActivity() {
        val intent = Intent(this, ClipboardReaderActivity::class.java)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }

    override fun onDestroy() {
        super.onDestroy()
        if (::floatingView.isInitialized) {
            windowManager.removeView(floatingView)
        }
    }
}
