package ch.pete.adbclipboard

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * Notification that guarantees the floating bubble is always recoverable:
 * whenever it is hidden, a persistent "tap to show" notification is posted.
 */
object BubbleNotifications {

    private const val CHANNEL_ID = "bubble_control"
    private const val NOTIFICATION_ID_HIDDEN = 1001

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val channel = NotificationChannel(
                CHANNEL_ID,
                context.getString(R.string.bubble_notification_channel),
                NotificationManager.IMPORTANCE_LOW
            )
            manager.createNotificationChannel(channel)
        }
    }

    /** Shows a "bubble hidden, tap to show" notification that restarts the service. */
    fun showBubbleHiddenNotification(context: Context) {
        ensureChannel(context)

        val showIntent = Intent(context, FloatingViewService::class.java)
        val pendingIntent = PendingIntent.getService(
            context,
            0,
            showIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val notification = Notification.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_qs_tile)
            .setContentTitle(context.getString(R.string.bubble_hidden_notification_title))
            .setContentText(context.getString(R.string.bubble_hidden_notification_text))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID_HIDDEN, notification)
    }

    /** Removes the "bubble hidden" notification once the service is running again. */
    fun cancelBubbleHiddenNotification(context: Context) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.cancel(NOTIFICATION_ID_HIDDEN)
    }
}
