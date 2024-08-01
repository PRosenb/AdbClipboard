package ch.pete.adbclipboard

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent


/*
 * Receives the implicit broadcast and reads the clipboard
 */
class ReadReceiver : BroadcastReceiver() {
    internal companion object {
        // return values
        const val ACTIVITY_RESULT_EMPTY_CLIPBOARD = 2
    }

    override fun onReceive(context: Context, intent: Intent) {
        context.startService(Intent(context, LogcatMonitoringService::class.java))

        val clipboardManager = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = clipboardManager.primaryClip
        if (clip != null && clip.itemCount > 0 && clip.getItemAt(0).text != null) {
            resultData = clip.getItemAt(0).text.toString()
            resultCode = Activity.RESULT_OK
        } else {
            resultData = ""
            resultCode = ACTIVITY_RESULT_EMPTY_CLIPBOARD
        }
    }
}
