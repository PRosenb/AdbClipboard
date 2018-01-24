package ch.pete.adbclipboard

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

import java.util.concurrent.CountDownLatch

/**
 * Allows to block test execution until a broadcast is received.
 * Created by peterrosenberg on 21/06/2017.
 */
class BlockingReceiver : BroadcastReceiver() {
    private val latch = CountDownLatch(1)
    private var intent: Intent? = null

    fun waitUntilOnReceiveIsCalled(): Intent? {
        try {
            latch.await()
        } catch (e: InterruptedException) {
            throw RuntimeException(e)
        }

        return intent
    }

    override fun onReceive(context: Context, intent: Intent) {
        this.intent = intent
        latch.countDown()
    }
}
