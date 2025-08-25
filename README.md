# AdbClipboard

[![GitHub Repository](https://img.shields.io/badge/GitHub-AdbClipboard-blue?logo=github)](https://github.com/PRosenb/AdbClipboard)
[![Google Play](https://img.shields.io/badge/Google%20Play-Download-green?logo=googleplay)](https://play.google.com/store/apps/details?id=ch.pete.adbclipboard)

AdbClipboard is a lightweight Android application that enables seamless clipboard synchronization
between your smartphone and PC using ADB (Android Debug Bridge).

## Why AdbClipboard?

While there are multiple clipboard sharing solutions that rely on external servers or cloud
services, developers in restricted environments often find these options blocked. Banks, government
agencies, and enterprise environments frequently prohibit access to third-party clipboard services
for security reasons.

AdbClipboard solves this problem by working entirely through your local ADB connection - no external
servers, no internet dependency, no data leaving your secure network. It's the perfect solution for
developers who need clipboard sync in security-conscious environments.

## Features

✨ **Simple & Lightweight** - Minimal footprint with a simple interface  
🔄 **Bidirectional Sync** - Copy content between Android and PC clipboards  
⚡ **Auto PC-to-Android** - Automatically syncs PC clipboard changes to your device  
🎯 **Manual Android-to-PC** - Tap the floating window to sync Android clipboard to PC  
📱 **Overlay Permission** - Uses display overlay to access clipboard when needed  
🌐 **Multiple Connections** - Supports both USB and WiFi connections

## How It Works

AdbClipboard uses a Python script on your PC to facilitate clipboard synchronization between your
computer and Android device through ADB.

**PC → Android (Automatic)**: When your PC clipboard changes, the content is automatically pushed to
your Android device's clipboard.

**Android → PC (Manual)**: Due to Android's security restrictions, you need to tap the AdbClipboard
floating window to read the Android clipboard and transfer it to your PC.

### Android Clipboard Restrictions

Android enforces strict limitations on clipboard access for security reasons. Apps can only read the
clipboard when displaying a visible interface - background services and floating windows alone are
insufficient. AdbClipboard works around this by providing a floating window that, when tapped,
briefly activates the app to read the clipboard before closing automatically.

## Installation

The setup requires installing both the Android app and the Python script on your development
machine.

### Android App Installation

Download and install
the [AdbClipboard app](https://play.google.com/store/apps/details?id=ch.pete.adbclipboard) from
Google Play Store.

**Required Permissions:**

- Display over other apps (for floating window)
- ADB debugging enabled on your device

### Python Script Setup

1. **Download**: Get the [latest release](https://github.com/PRosenb/AdbClipboard/releases/latest)
2. **Extract**: Uncompress the downloaded file to get the **AdbClipboard-x.y.z** folder

#### macOS/Linux Setup

```bash
# Copy the script to your home directory
cp ./adb_clipboard_sync.py ~/

# Make the script executable
chmod +x ~/adb_clipboard_sync.py

# Run the script
~/adb_clipboard_sync.py
```

### Prerequisites

- **ADB Tools**: Ensure Android Debug Bridge is installed and accessible
- **Python 3.x**: Required to run the synchronization script
- **USB Debugging**: Must be enabled on your Android device
- **Device Authorization**: Accept the ADB debugging prompt on your device

## Usage

1. Connect your Android device via USB or WiFi ADB
2. Launch the Python script on your PC
3. Enable the floating window permission for AdbClipboard (if not already enabled)
4. Start the AdbClipboard app to display the floating window
5. Copy text on your PC - it automatically appears on Android
6. To copy from Android to PC, tap the AdbClipboard floating window

## Troubleshooting

**Script not connecting?**

- Verify ADB is installed and in your PATH
- Check USB debugging is enabled
- Ensure device is authorized for debugging

**Floating window not appearing?**

- Grant "Display over other apps" permission in Android settings
- Restart the AdbClipboard app after granting permission

## Contributions

We welcome contributions! Whether it's bug fixes, feature enhancements, or documentation
improvements, your input helps make AdbClipboard better for everyone.

**Ways to contribute:**

- Report issues and bugs
- Create pull requests
- Improve documentation
- Share usage tips and tricks

---

*Made with ❤️ for developers who need seamless clipboard sync between Android and PC*

## Developer Commands

For developers who want to test or integrate AdbClipboard functionality directly, you can use these
ADB commands:

### Write to Android

```bash
adb shell am broadcast -a ch.pete.adbclipboard.WRITE -n ch.pete.adbclipboard/.WriteReceiver -e text "Text for the clipboard"
```

### Read from Android

```bash
adb shell cat /sdcard/Android/data/ch.pete.adbclipboard/files/clipboard.txt
```

These commands allow you to programmatically interact with AdbClipboard without using the Python
script, which can be useful for automation or custom integrations.