package ch.pete.adbclipboard

import android.app.PendingIntent
import android.content.Intent
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

/**
 * Quick Settings tile that performs the same action as tapping the floating bubble:
 * briefly opens [ClipboardReaderActivity] to read the device clipboard and write it
 * to the file the PC-side script picks up.
 */
class ClipboardTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        qsTile?.apply {
            state = Tile.STATE_ACTIVE
            updateTile()
        }
    }

    override fun onClick() {
        super.onClick()
        // Reading the clipboard while the device is locked would fail silently or
        // expose content unexpectedly; only act when the user is unlocked.
        if (isLocked()) {
            return
        }
        val intent = Intent(this, ClipboardReaderActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        startActivityAndCollapse(pendingIntent)
    }
}
