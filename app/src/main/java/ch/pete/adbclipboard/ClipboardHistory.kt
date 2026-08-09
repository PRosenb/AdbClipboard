package ch.pete.adbclipboard

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * On-device clipboard history of synced items. Stored in app-internal storage
 * (not the external/ADB-readable directory) so history stays private.
 */
object ClipboardHistory {

    data class Entry(val timestamp: Long, val text: String)

    private const val FILE_NAME = "clipboard_history.json"
    private const val MAX_ENTRIES = 50

    @Synchronized
    fun add(context: Context, text: String) {
        if (text.isBlank()) return
        val entries = load(context).toMutableList()
        // Move to the top and drop exact duplicates
        entries.removeAll { it.text == text }
        entries.add(0, Entry(System.currentTimeMillis(), text))
        while (entries.size > MAX_ENTRIES) {
            entries.removeAt(entries.size - 1)
        }
        save(context, entries)
    }

    @Synchronized
    fun load(context: Context): List<Entry> {
        val file = historyFile(context)
        if (!file.exists()) return emptyList()
        return try {
            val array = JSONArray(file.readText())
            (0 until array.length()).map { i ->
                val obj = array.getJSONObject(i)
                Entry(obj.getLong("timestamp"), obj.getString("text"))
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    @Synchronized
    fun remove(context: Context, timestamp: Long) {
        save(context, load(context).filterNot { it.timestamp == timestamp })
    }

    @Synchronized
    fun clear(context: Context) {
        historyFile(context).delete()
    }

    private fun save(context: Context, entries: List<Entry>) {
        val array = JSONArray()
        entries.forEach {
            array.put(JSONObject().put("timestamp", it.timestamp).put("text", it.text))
        }
        historyFile(context).writeText(array.toString())
    }

    private fun historyFile(context: Context): File =
        File(context.filesDir, FILE_NAME)
}
