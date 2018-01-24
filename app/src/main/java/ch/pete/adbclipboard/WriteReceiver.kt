package ch.pete.adbclipboard

import android.app.Activity
import android.content.*
import android.media.RingtoneManager
import android.text.TextUtils
import timber.log.Timber
import java.io.UnsupportedEncodingException
import java.net.URLDecoder

/*
 * Receives implicit broadcast and writes to the clipboard
 */
class WriteReceiver : BroadcastReceiver() {
    internal companion object {
        // arguments
        const val EXTRA_TEXT = "text"

        // return values
        const val RESULT_SUCCESS = "SUCCESS"
        const val RESULT_SUCCESS_ALREADY_SET = "SUCCESS_ALREADY_SET"
        const val RESULT_NO_TEXT = "NO_TEXT"
        const val RESULT_UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"

        const val ACTIVITY_RESULT_NO_TEXT = 3
        const val ACTIVITY_RESULT_UNSUPPORTED_ENCODING = 4
    }

    override fun onReceive(context: Context, intent: Intent) {
        val encodedText = intent.getStringExtra(EXTRA_TEXT)
        if (TextUtils.isEmpty(encodedText)) {
            resultData = RESULT_NO_TEXT
            resultCode = ACTIVITY_RESULT_NO_TEXT
            return
        }

        try {
            val text = URLDecoder.decode(encodedText, "UTF-8")
            val clipboardManager = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val existingClip = clipboardManager.primaryClip

            if (existingClip == null
                    || existingClip.itemCount == 0
                    || existingClip.getItemAt(0).text != text) {

                val clip = ClipData.newPlainText(text, text)
                clipboardManager.primaryClip = clip

                // play notification tone
                val notification = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
                val ringtone = RingtoneManager.getRingtone(context, notification)
                ringtone.play()

                resultData = RESULT_SUCCESS
                resultCode = Activity.RESULT_OK
            } else {
                resultData = RESULT_SUCCESS_ALREADY_SET
                resultCode = Activity.RESULT_OK
            }
        } catch (e: UnsupportedEncodingException) {
            Timber.e(e)
            resultData = RESULT_UNSUPPORTED_ENCODING
            resultCode = ACTIVITY_RESULT_UNSUPPORTED_ENCODING
        }
    }
}
