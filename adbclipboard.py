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


def checkAdbDependency():
    try:
        result = subprocess.run(['adb'], capture_output=True, text=True)
        return True
    except OSError as e:
        print("adb not found. Please make sure Android SDK is installed" +
              " and adb is available on your PATH.")
        if verbose is True:
            print("error: {0}".format(e))
        return False


def getConnectedDeviceHashes():
    result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
    adbDevicesOutputLines = result.stdout.splitlines()

    # remove first line that contains a description
    del adbDevicesOutputLines[0]

    deviceHashes = []
    for deviceLine in adbDevicesOutputLines:
        if (len(deviceLine) > 0):
            deviceHashes.append(deviceLine.split('\t')[0])
    return deviceHashes


def urlEncode(unencodedString):
    return parse.quote_plus(unencodedString)


def writeToDevice(deviceHash, urlEncodedString):
    result = subprocess.run([
        'adb',
        '-s', deviceHash,
        'shell', 'am',
        'broadcast',
        '-n', 'ch.pete.adbclipboard/.WriteReceiver',
        '-e', 'text', urlEncodedString
    ], capture_output=True, text=True)
    
    if verbose is True:
        print("write device response from {0}:\n{1}".format(
            deviceHash, result.stdout))
    return parseBroadcastResponse(result.stdout)


def readFromDevice(deviceHash):
    file_path = "/sdcard/Android/data/ch.pete.adbclipboard/files/clipboard.txt"

    # Try to read the file
    result = subprocess.run([
        'adb', '-s', deviceHash, 'shell', 'cat', file_path
    ], capture_output=True, text=True)
    
    response = Response()
    if result.stderr:
        resultMatcher = re.compile("^.*No such file or directory\n")
        if resultMatcher.match(result.stderr):
            response.status = -1
            response.data = ""
        else:
            print("read file error from {0}:\n{1}"
                  .format(deviceHash, result.stderr))
            response.status = 1
    else:
        response.status = -1
        # Remove the file after reading
        rm_result = subprocess.run([
            'adb', '-s', deviceHash, 'shell', 'rm', file_path
        ], capture_output=True, text=True)
        
        if verbose is True:
            print("rm response {0}: {1}"
                  .format(rm_result.stdout, rm_result.stderr))

    file_content = result.stdout
    if file_content != "":
        print("read from {0}: {1}"
              .format(deviceHash, file_content))
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
        result = subprocess.run(['pbpaste'], capture_output=True, text=True)
        return result.stdout

    def writeClipboard(self, text):
        subprocess.run(['pbcopy'], input=text, text=True)


class ClipboardHandlerLinux(object):
    def checkDependencies(self):
        try:
            subprocess.run(['xclip'], capture_output=True, text=True)
            return True
        except OSError as e:
            print("xclip not found." +
                  " Please install it with your package manager.")
            print("e.g. sudo apt install xclip")
            if verbose is True:
                print("error: {0}".format(e))
            return False

    def readClipboard(self):
        result = subprocess.run(['xclip', '-o'], capture_output=True, text=True)
        return result.stdout

    def writeClipboard(self, text):
        subprocess.run(['xclip'], input=text, text=True)


if platform.system() == "Linux":
    clipboardHandler = ClipboardHandlerLinux()
else:
    clipboardHandler = ClipboardHandlerMac()

parseArgs()
if checkAdbDependency() is True:
    if clipboardHandler.checkDependencies() is True:
        syncWithDevices(clipboardHandler)
