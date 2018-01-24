package ch.pete.adbclipboard

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.support.test.InstrumentationRegistry
import java.util.concurrent.CountDownLatch

/**
 * Base class of the tests. Contains helper methods.
 * Created by peter.rosenberg on 18/2/18.
 */
open class BaseTest {
    internal fun directClipboardWrite(text: String) {
        doOnMainThreadAndWait {
            val clipboardManager = InstrumentationRegistry.getTargetContext()
                    .getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

            val clip = ClipData.newPlainText(text, text)
            clipboardManager.primaryClip = clip
        }
    }

    internal fun directClipboardRead(): String? {
        return doOnMainThreadAndWait<String?> {
            val clipboardManager = InstrumentationRegistry.getTargetContext()
                    .getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

            clipboardManager.primaryClip.getItemAt(0).text.toString()
        }
    }

    internal fun directClipboardClear() {
        doOnMainThreadAndWait {
            val clipboardManager = InstrumentationRegistry.getTargetContext()
                    .getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

            val clip = ClipData.newPlainText(null, null)
            clipboardManager.primaryClip = clip
        }
    }

    private fun <T> doOnMainThreadAndWait(functionOnMainThread: () -> T): T? {
        val latch = CountDownLatch(1)
        var t: T? = null

        Handler(Looper.getMainLooper()).post({
            t = functionOnMainThread()
            latch.countDown()
        })
        latch.await()
        return t
    }
}
