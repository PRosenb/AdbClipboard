#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import platform
import re
import subprocess
import time
from urllib import parse

# Constants
CONNECTED_DEVICES_DELAY_DEFAULT = 5
NO_CONNECTED_DEVICE_DELAY_DEFAULT = 60

verbose = False
connectedDevicesDelay = CONNECTED_DEVICES_DELAY_DEFAULT
noConnectedDeviceDelay = NO_CONNECTED_DEVICE_DELAY_DEFAULT


def parseArgs():
    parser = argparse.ArgumentParser(
        description='Sync clipboard with connected Android devices.')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Output status on the console')
    parser.add_argument('-c', '--connected-devices-delay', type=int,
                        help="Delay in seconds between each sync if there is" +
                        " at least one device connected." +
                        " Defaults to {0} seconds."
                        .format(CONNECTED_DEVICES_DELAY_DEFAULT))
    parser.add_argument('-n', '--no-connected-device-delay', type=int,
                        help="Delay in seconds between each sync if there is" +
                        " no device connected. Defaults to {0} seconds."
                        .format(NO_CONNECTED_DEVICE_DELAY_DEFAULT))

    args = parser.parse_args()
    global verbose, connectedDevicesDelay, noConnectedDeviceDelay
    if args.verbose is True:
        verbose = True
    if args.connected_devices_delay is not None:
        connectedDevicesDelay = args.connected_devices_delay
    if args.no_connected_device_delay is not None:
        noConnectedDeviceDelay = args.no_connected_device_delay

    if verbose is True:
        print("verbose: {0}".format(verbose))
        print("connectedDevicesDelay: {0}".format(connectedDevicesDelay))
        print("noConnectedDeviceDelay: {0}".format(noConnectedDeviceDelay))
        print()


def runExternalCommand(cmd, timeout=30, input_text=None, context="command"):
    """
    Centralized method to run external commands with consistent error handling

    Args:
        cmd: List of command arguments
        timeout: Timeout in seconds
        input_text: Text to send to stdin (optional)
        context: Description of the command for error messages

    Returns:
        CompletedProcess object or None if failed
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text
        )

        if verbose and result.returncode != 0:
            print("{0} failed with return code: {1}".format(context, result.returncode))
            if result.stderr:
                print("Error output: {0}".format(result.stderr))

        return result

    except FileNotFoundError:
        print("{0} not found: {1}".format(context, cmd[0]))
        return None
    except subprocess.TimeoutExpired:
        print("{0} timed out after {1}s".format(context, timeout))
        return None
    except Exception as e:
        print("Error running {0}: {1}".format(context, e))
        return None


def runAdbCommand(args, timeout=30, input_text=None, context="adb command"):
    """Run ADB command with centralized error handling"""
    cmd = ['adb'] + args
    return runExternalCommand(cmd, timeout, input_text, context)


def runPbCommand(command, timeout=10, input_text=None):
    """Run macOS clipboard command (pbcopy/pbpaste) with centralized error handling"""
    context = "macOS {0} command".format(command)
    return runExternalCommand([command], timeout, input_text, context)


def runXclipCommand(args, timeout=10, input_text=None):
    """Run Linux xclip command with centralized error handling"""
    cmd = ['xclip'] + args
    context = "Linux xclip command"
    return runExternalCommand(cmd, timeout, input_text, context)


def checkAdbDependency():
    result = runAdbCommand([], timeout=10, context="adb dependency check")
    return result is not None


def getConnectedDeviceHashes():
    result = runAdbCommand(['devices'], context="adb devices")
    if result is None or result.returncode != 0:
        return []

    adbDevicesOutputLines = result.stdout.splitlines()

    # remove first line that contains a description
    if len(adbDevicesOutputLines) > 0:
        del adbDevicesOutputLines[0]

    deviceHashes = []
    for deviceLine in adbDevicesOutputLines:
        if (len(deviceLine) > 0):
            deviceHashes.append(deviceLine.split('\t')[0])
    return deviceHashes


def urlEncode(unencodedString):
    return parse.quote_plus(unencodedString)


def writeToDevice(deviceHash, urlEncodedString):
    result = runAdbCommand([
        '-s', deviceHash,
        'shell', 'am',
        'broadcast',
        '-n', 'ch.pete.adbclipboard/.WriteReceiver',
        '-e', 'text', urlEncodedString
    ], context="write to device {0}".format(deviceHash))

    if result is None or result.returncode != 0:
        # Return error response
        response = Response()
        response.status = 1
        return response

    if verbose is True:
        print("write device response from {0}:\n{1}".format(
            deviceHash, result.stdout))
    return parseBroadcastResponse(result.stdout)


def readFromDevice(deviceHash):
    file_path = "/sdcard/Android/data/ch.pete.adbclipboard/files/clipboard.txt"
    
    response = Response()

    # Try to read the file
    result = runAdbCommand([
        '-s', deviceHash, 'shell', 'cat', file_path
    ], context="read from device {0}".format(deviceHash))

    if result is None:
        response.status = 1
        response.data = ""
        return response

    if result.stderr:
        resultMatcher = re.compile("^.*No such file or directory")
        if resultMatcher.match(result.stderr):
            response.status = -1
            response.data = ""
            return response
        else:
            print("read file error from {0}:\n{1}".format(deviceHash, result.stderr))
            response.status = 1
            response.data = ""
            return response

    if result.returncode != 0:
        response.status = 1
        response.data = ""
        return response

    response.status = -1
    file_content = result.stdout

    # Remove the file after reading (only if read was successful)
    rm_result = runAdbCommand([
        '-s', deviceHash, 'shell', 'rm', file_path
    ], timeout=10, context="remove file from device {0}".format(deviceHash))

    if verbose is True and rm_result:
        print("rm response stdout: {0}, stderr: {1}".format(
            rm_result.stdout, rm_result.stderr))

    if file_content != "":
        print("read from {0}: {1}".format(deviceHash, file_content))
    response.data = file_content
    return response


class Response(object):
    status = None
    data = None


def parseBroadcastResponse(resultString):
    resultMatcher = re.compile("^.*\n.*result=([\-]{0,1}[0-9]*).*")
    resultMatch = resultMatcher.match(resultString)
    response = Response()
    if resultMatch and len(resultMatch.groups()) > 0:
        if len(resultMatch.group(1)) == 0:
            print("error: " + resultMatch.group(1))
        response.status = int(resultMatch.group(1))
        if response.status == -1:
            # re.DOTALL to match newline as well
            dataMatcher = re.compile("^.*\n.*data=\"(.*)\"$", re.DOTALL)
            dataMatch = dataMatcher.match(resultString)
            if dataMatch and len(dataMatch.groups()) > 0:
                response.data = dataMatch.group(1)
    return response


def syncWithDevices(clipboardHandler):
    previousClipboardString = None
    while True:
        deviceHashes = getConnectedDeviceHashes()

        hasDeviceWithAdbClipboardInstalled = False
        hasUpdateFromDevice = False
        if (len(deviceHashes) == 0):
            # no devices connected, sleep longer
            print("No device connected, sleep for {0}s"
                  .format(noConnectedDeviceDelay))
            previousClipboardString = None
            time.sleep(noConnectedDeviceDelay)
        else:
            clipboardString = clipboardHandler.readClipboard()
            if previousClipboardString != clipboardString:
                previousClipboardString = clipboardString

                if len(clipboardString) > 0:
                    urlEncodedString = urlEncode(clipboardString)
                    for deviceHash in deviceHashes:
                        response = writeToDevice(
                            deviceHash, urlEncodedString)
                        printedStatus = ""
                        if response.status == -1:
                            hasDeviceWithAdbClipboardInstalled = True
                        else:
                            printedStatus = " (failed)"
                        print("write to {0}: {1}{2}".format(
                            deviceHash, clipboardString, printedStatus))
            else:
                for deviceHash in deviceHashes:
                    response = readFromDevice(deviceHash)
                    if response.status == -1:
                        hasDeviceWithAdbClipboardInstalled = True
                    deviceClipboardText = response.data

                    if len(clipboardString) == 0 or \
                            deviceClipboardText != clipboardString:
                        if deviceClipboardText is not None and deviceClipboardText != "":
                            if verbose is True:
                                print("write to clipboard: {0}".format(
                                    deviceClipboardText))
                            clipboardHandler.writeClipboard(deviceClipboardText)
                            hasUpdateFromDevice = True
                            previousClipboardString = deviceClipboardText
                            break
            if hasDeviceWithAdbClipboardInstalled is False:
                print("No device with installed AdbClipboard, sleep for {0}s"
                      .format(noConnectedDeviceDelay))
                previousClipboardString = None
                time.sleep(noConnectedDeviceDelay)
            elif hasUpdateFromDevice is False:
                time.sleep(connectedDevicesDelay)


class ClipboardHandlerMac(object):
    def checkDependencies(self):
        # on Mac pbpaste is preinstalled
        return True

    def readClipboard(self):
        result = runPbCommand('pbpaste')
        if result is None or result.returncode != 0:
            return ""
        return result.stdout

    def writeClipboard(self, text):
        result = runPbCommand('pbcopy', input_text=text)
        # writeClipboard doesn't need to return anything, errors are handled by runPbCommand


class ClipboardHandlerLinux(object):
    def checkDependencies(self):
        result = runXclipCommand(['-version'])
        return result is not None and result.returncode == 0

    def readClipboard(self):
        result = runXclipCommand(['-o'])
        if result is None or result.returncode != 0:
            return ""
        return result.stdout

    def writeClipboard(self, text):
        result = runXclipCommand([], input_text=text)
        # writeClipboard doesn't need to return anything, errors are handled by runXclipCommand


if platform.system() == "Linux":
    clipboardHandler = ClipboardHandlerLinux()
else:
    clipboardHandler = ClipboardHandlerMac()

parseArgs()
if checkAdbDependency() is True:
    if clipboardHandler.checkDependencies() is True:
        syncWithDevices(clipboardHandler)
