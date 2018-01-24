package ch.pete.adbclipboard

import android.app.Activity
import android.content.Intent
import android.support.test.InstrumentationRegistry
import android.support.test.runner.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Tests the WriteReceiver.
 * Created by peter.rosenberg on 17/1/18.
 */
@RunWith(AndroidJUnit4::class)
class WriteReceiverTest : BaseTest() {
    @Test
    fun writeClipboard_success() {
        directClipboardWrite("other text")
        val testText = "test text"

        val writeIntent = Intent(InstrumentationRegistry.getTargetContext(), WriteReceiver::class.java)
        writeIntent.putExtra(WriteReceiver.EXTRA_TEXT, testText)

        val blockingReceiver = BlockingReceiver()
        InstrumentationRegistry.getTargetContext().sendOrderedBroadcast(
                writeIntent, null, blockingReceiver, null, 0, null, null)
        blockingReceiver.waitUntilOnReceiveIsCalled()

        assertEquals("Wrong resultCode", Activity.RESULT_OK, blockingReceiver.resultCode)
        assertEquals("Wrong resultData", WriteReceiver.RESULT_SUCCESS, blockingReceiver.resultData)

        assertEquals("wrong value in clipboard", testText, directClipboardRead())
    }

    @Test
    fun writeClipboard_successAlreadySet() {
        val testText = "test text"
        directClipboardWrite(testText)

        val writeIntent = Intent(InstrumentationRegistry.getTargetContext(), WriteReceiver::class.java)
        writeIntent.putExtra(WriteReceiver.EXTRA_TEXT, testText)

        val blockingReceiver = BlockingReceiver()
        InstrumentationRegistry.getTargetContext().sendOrderedBroadcast(
                writeIntent, null, blockingReceiver, null, 0, null, null)
        blockingReceiver.waitUntilOnReceiveIsCalled()

        assertEquals("Wrong resultCode", Activity.RESULT_OK, blockingReceiver.resultCode)
        assertEquals("Wrong resultData", WriteReceiver.RESULT_SUCCESS_ALREADY_SET, blockingReceiver.resultData)

        assertEquals("wrong value in clipboard", testText, directClipboardRead())
    }

    @Test
    fun writeClipboard_noText() {
        val previousText = "previous text"
        directClipboardWrite(previousText)

        val writeIntent = Intent(InstrumentationRegistry.getTargetContext(), WriteReceiver::class.java)

        val blockingReceiver = BlockingReceiver()
        InstrumentationRegistry.getTargetContext().sendOrderedBroadcast(
                writeIntent, null, blockingReceiver, null, 0, null, null)
        blockingReceiver.waitUntilOnReceiveIsCalled()

        assertEquals("Wrong resultCode", WriteReceiver.ACTIVITY_RESULT_NO_TEXT, blockingReceiver.resultCode)
        assertEquals("Wrong resultData", WriteReceiver.RESULT_NO_TEXT, blockingReceiver.resultData)

        assertEquals("wrong value in clipboard", previousText, directClipboardRead())
    }
}
