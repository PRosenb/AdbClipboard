package ch.pete.adbclipboard

import android.app.Activity
import android.content.Intent
import android.support.test.InstrumentationRegistry
import android.support.test.runner.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Tests the ReadReceiver.
 * Created by peter.rosenberg on 17/1/18.
 */
@RunWith(AndroidJUnit4::class)
class ReadReceiverTest : BaseTest() {
    @Test
    fun readClipboard_success() {
        val testText = "test text"
        directClipboardWrite(testText)

        val readIntent = Intent(InstrumentationRegistry.getTargetContext(), ReadReceiver::class.java)

        val blockingReceiver = BlockingReceiver()
        InstrumentationRegistry.getTargetContext().sendOrderedBroadcast(
                readIntent, null, blockingReceiver, null, 0, null, null)
        blockingReceiver.waitUntilOnReceiveIsCalled()

        assertEquals("Wrong resultCode", Activity.RESULT_OK, blockingReceiver.resultCode)
        assertEquals("Wrong resultData", testText, blockingReceiver.resultData)
    }

    @Test
    fun readClipboard_empty() {
        directClipboardClear()

        val readIntent = Intent(InstrumentationRegistry.getTargetContext(), ReadReceiver::class.java)

        val blockingReceiver = BlockingReceiver()
        InstrumentationRegistry.getTargetContext().sendOrderedBroadcast(
                readIntent, null, blockingReceiver, null, 0, null, null)
        blockingReceiver.waitUntilOnReceiveIsCalled()

        assertEquals("Wrong resultCode", ReadReceiver.ACTIVITY_RESULT_EMPTY_CLIPBOARD,
                blockingReceiver.resultCode)
        assertEquals("Wrong resultData", "", blockingReceiver.resultData)
    }
}
