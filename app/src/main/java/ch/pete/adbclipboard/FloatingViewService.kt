package ch.pete.adbclipboard

import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.Point
import android.os.IBinder
import android.util.DisplayMetrics
import android.view.GestureDetector
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import kotlin.math.abs

/**
 * Floating bubble that:
 *  - tap (single tap confirmed): reads the clipboard for the PC script
 *  - drag: moves the bubble, then snaps it to the nearest horizontal edge
 *  - drag/fling far off-screen or fast: dismisses the bubble
 *  - double-tap: hides the bubble
 */
class FloatingViewService : Service() {

    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private lateinit var gestureDetector: GestureDetector

    // Gesture state
    private var isDragging = false
    private var longPressed = false
    private var fingerDown = false

    // Drag bookkeeping
    private var initialX = 0
    private var initialY = 0
    private var initialTouchX = 0f
    private var initialTouchY = 0f

    // Fling velocity estimation (based on raw screen coords, immune to window moves)
    private var lastMoveRawX = 0f
    private var lastMoveTime = 0L
    private var lastVelocityX = 0f

    private var positionAnimator: ValueAnimator? = null

    override fun onBind(intent: Intent?): IBinder? = null

    @SuppressLint("InflateParams")
    override fun onCreate() {
        super.onCreate()

        // The bubble is back: clear any "bubble hidden" notification and set up the channel.
        BubbleNotifications.ensureChannel(this)
        BubbleNotifications.cancelBubbleHiddenNotification(this)

        floatingView = LayoutInflater.from(this).inflate(R.layout.floating_widget, null)

        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onDown(e: MotionEvent): Boolean = true

            override fun onSingleTapConfirmed(e: MotionEvent): Boolean {
                // The only path that reads the clipboard. A drag sets isDragging and
                // cancels the tap region, so dragging can never trigger a copy.
                if (!isDragging && !longPressed) {
                    startClipboardReaderActivity()
                }
                return true
            }

            override fun onDoubleTap(e: MotionEvent): Boolean {
                // Double-tap hides the bubble. Long-press deliberately does NOT hide:
                // every drag starts with a press, so long-press would fire whenever
                // the user holds briefly before moving the bubble.
                hideBubble()
                return true
            }
        })

        // Keeps the bubble clickable for accessibility (TalkBack) and programmatic clicks.
        // Real finger interaction goes through the touch listener + gesture detector.
        floatingView.setOnClickListener {
            if (!fingerDown && !isDragging && !longPressed) {
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

        view.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    fingerDown = true
                    isDragging = false
                    longPressed = false
                    positionAnimator?.cancel()
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    lastMoveRawX = event.rawX
                    lastMoveTime = System.currentTimeMillis()
                    lastVelocityX = 0f
                    gestureDetector.onTouchEvent(event)
                    true
                }

                MotionEvent.ACTION_MOVE -> {
                    val now = System.currentTimeMillis()
                    val dx = event.rawX - initialTouchX
                    val dy = event.rawY - initialTouchY
                    if (!isDragging &&
                        (abs(dx) > dragThreshold || abs(dy) > dragThreshold)) {
                        isDragging = true
                    }
                    if (isDragging) {
                        params.x = initialX + dx.toInt()
                        params.y = initialY + dy.toInt()
                        windowManager.updateViewLayout(view, params)

                        val elapsed = now - lastMoveTime
                        if (elapsed > 0) {
                            lastVelocityX = (event.rawX - lastMoveRawX) * 1000f / elapsed
                        }
                        lastMoveRawX = event.rawX
                        lastMoveTime = now
                    }
                    // Once dragging, stop feeding the detector: the window follows the finger,
                    // so its local coordinates barely change and it would misread the gesture
                    // (e.g. long-press firing while aiming at the edge).
                    if (!isDragging) {
                        gestureDetector.onTouchEvent(event)
                    }
                    true
                }

                MotionEvent.ACTION_UP -> {
                    fingerDown = false
                    if (isDragging) {
                        // Reset the detector's internal state so the finished drag can't be
                        // mistaken for a tap/double-tap later.
                        gestureDetector.onTouchEvent(obtainCancel(event))
                        endDrag(params)
                    } else {
                        gestureDetector.onTouchEvent(event)
                    }
                    true
                }

                MotionEvent.ACTION_CANCEL -> {
                    fingerDown = false
                    isDragging = false
                    gestureDetector.onTouchEvent(event)
                    true
                }

                else -> {
                    if (!isDragging) {
                        gestureDetector.onTouchEvent(event)
                    }
                    true
                }
            }
        }
    }

    private fun obtainCancel(event: MotionEvent): MotionEvent {
        val cancel = MotionEvent.obtain(event)
        cancel.action = MotionEvent.ACTION_CANCEL
        return cancel
    }

    /**
     * Called when a drag ends: dismiss if flung/dragged far off-screen, otherwise
     * snap to the nearest horizontal edge.
     */
    private fun endDrag(params: WindowManager.LayoutParams) {
        val screenSize = getScreenSize()
        val viewWidth = floatingView.width
        val viewHeight = floatingView.height
        val centerX = params.x + viewWidth / 2f

        val totalDx = params.x - initialX
        // A fast move only counts as a dismiss fling if the bubble actually travelled a
        // real distance - otherwise slight, quick nudges would hide it by accident.
        val flungOff = abs(lastVelocityX) > FLING_DISMISS_VELOCITY &&
            abs(totalDx) > MIN_FLING_DISTANCE
        val draggedOff = centerX <= 0f || centerX >= screenSize.x
        if (flungOff || draggedOff) {
            dismissBubble(params, centerX < screenSize.x / 2f, screenSize.x)
            return
        }

        // Snap to the nearest horizontal edge and keep Y on screen
        val targetX = if (centerX < screenSize.x / 2f) {
            EDGE_MARGIN
        } else {
            screenSize.x - viewWidth - EDGE_MARGIN
        }
        val maxY = (screenSize.y - viewHeight).coerceAtLeast(0)
        val targetY = params.y.coerceIn(0, maxY)
        animateTo(params, targetX, targetY, SNAP_DURATION_MS) {}
    }

    private fun dismissBubble(params: WindowManager.LayoutParams, offLeft: Boolean, screenWidth: Int) {
        val viewWidth = floatingView.width
        val targetX = if (offLeft) {
            -viewWidth - DISMISS_OFFSET
        } else {
            screenWidth + DISMISS_OFFSET
        }
        animateTo(params, targetX, params.y, DISMISS_DURATION_MS) {
            BubbleNotifications.showBubbleHiddenNotification(this@FloatingViewService)
            stopSelf()
        }
    }

    private fun animateTo(
        params: WindowManager.LayoutParams,
        targetX: Int,
        targetY: Int,
        duration: Long,
        onEnd: () -> Unit
    ) {
        positionAnimator?.cancel()
        val startX = params.x
        val startY = params.y
        val animator = ValueAnimator.ofFloat(0f, 1f).apply {
            this.duration = duration
            interpolator = DecelerateInterpolator()
            addUpdateListener {
                val fraction = it.animatedFraction
                params.x = startX + ((targetX - startX) * fraction).toInt()
                params.y = startY + ((targetY - startY) * fraction).toInt()
                if (::floatingView.isInitialized) {
                    windowManager.updateViewLayout(floatingView, params)
                }
            }
            addListener(object : android.animation.AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: android.animation.Animator) {
                    onEnd()
                }
            })
            start()
        }
        positionAnimator = animator
    }

    @Suppress("DEPRECATION")
    private fun getScreenSize(): Point {
        // getRealMetrics covers the full display including system bars, which is what
        // overlay windows are positioned against. Deprecated on API 30+ but still works.
        val metrics = DisplayMetrics()
        windowManager.defaultDisplay.getRealMetrics(metrics)
        return Point(metrics.widthPixels, metrics.heightPixels)
    }

    private fun hideBubble() {
        longPressed = true
        positionAnimator?.cancel()
        // Guarantee a way back: show a persistent "tap to show" notification.
        BubbleNotifications.showBubbleHiddenNotification(this)
        stopSelf()
    }

    private fun startClipboardReaderActivity() {
        val intent = Intent(this, ClipboardReaderActivity::class.java)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }

    override fun onDestroy() {
        super.onDestroy()
        positionAnimator?.cancel()
        if (::floatingView.isInitialized) {
            windowManager.removeView(floatingView)
        }
    }

    companion object {
        private const val SNAP_DURATION_MS = 200L
        private const val DISMISS_DURATION_MS = 250L
        private const val DISMISS_OFFSET = 200
        private const val EDGE_MARGIN = 0
        private const val FLING_DISMISS_VELOCITY = 2000f
        private const val MIN_FLING_DISTANCE = 200
    }
}
