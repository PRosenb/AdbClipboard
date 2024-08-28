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
        noConnectedDeviceDelay = args.connected_devices_delay

    if verbose is True:
        print("verbose: {0}".format(verbose))
        print("connectedDevicesDelay: {0}".format(connectedDevicesDelay))
        print("noConnectedDeviceDelay: {0}".format(noConnectedDeviceDelay))
        print


def checkAdbDependency():
    try:
        process = subprocess.Popen(['adb'], stdout=subprocess.PIPE)
        return True
    except OSError as e:
        print("adb not found. Please make sure Android SDK is installed" +
              " and adb is available on your PATH.")
        if verbose is True:
            print("error: {0}".format(e))
        return False


def getConnectedDeviceHashes():
    adbProcess = subprocess.Popen(['adb', 'devices'], stdout=subprocess.PIPE)
    adbDevicesOutput = adbProcess.communicate()[0].decode("utf-8")
    adbDevicesOutputLines = adbDevicesOutput.splitlines()

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
    adbProcess = subprocess.Popen(
        ['adb',
            '-s', deviceHash,
            'shell', 'am',
            'broadcast',
            '-n', 'ch.pete.adbclipboard/.WriteReceiver',
            '-e', 'text', urlEncodedString],
        stdout=subprocess.PIPE)
    resultString = adbProcess.communicate()[0].decode("utf-8")
    if verbose is True:
        print("write device response from {0}:\n{1}".format(
            deviceHash, resultString))
    return parseResponse(resultString)


def readFromDevice(deviceHash):
    adbProcess = subprocess.Popen(
        ['adb',
            '-s', deviceHash,
            'shell', 'am',
            'broadcast',
            '-n', 'ch.pete.adbclipboard/.ReadReceiver'],
        stdout=subprocess.PIPE)
    resultString = adbProcess.communicate()[0].decode("utf-8")
    if verbose is True:
        print("read device response from {0}:\n{1}"
              .format(deviceHash, resultString))
    return parseResponse(resultString)


class Response(object):
    status = None
    data = None


def parseResponse(resultString):
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
            clipboardString = clipboardHandler.readClipboard().decode("utf-8")
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
                        print("send to {0}: \"{1}\"{2}".format(
                            deviceHash, clipboardString, printedStatus))
            else:
                for deviceHash in deviceHashes:
                    response = readFromDevice(deviceHash)
                    if response.status == -1:
                        hasDeviceWithAdbClipboardInstalled = True
                        deviceClipboardText = response.data

                        if len(clipboardString) == 0 or \
                                deviceClipboardText != clipboardString:
                            print("recv from {0}: \"{1}\"".format(
                                deviceHash, deviceClipboardText))
                            if deviceClipboardText is not None:
                                if verbose is True:
                                    print("write to clipboard: {0}".format(
                                        deviceClipboardText))
                                clipboardHandler.writeClipboard(
                                    deviceClipboardText.encode("utf-8"))
                                hasUpdateFromDevice = True
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
        process = subprocess.Popen(['pbpaste'], stdout=subprocess.PIPE)
        clipboardText = process.communicate()[0]
        return clipboardText

    def writeClipboard(self, text):
        process = subprocess.Popen(['pbcopy'],
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        process.communicate(input=text)


class ClipboardHandlerLinux(object):
    def checkDependencies(self):
        try:
            process = subprocess.Popen(['xclip'], stdout=subprocess.PIPE)
            return True
        except OSError as e:
            print("xclip not found." +
                  " Please install it with your package manager.")
            print("e.g. sudo apt install xclip")
            if verbose is True:
                print("error: {0}".format(e))
            return False

    def readClipboard(self):
        process = subprocess.Popen(['xclip'], stdout=subprocess.PIPE)
        clipboardText = process.communicate()[0]
        return clipboardText

    def writeClipboard(self, text):
        process = subprocess.Popen(['xclip', '-o'],
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        process.communicate(input=text)


if platform.system() == "Linux":
    clipboardHandler = ClipboardHandlerLinux()
else:
    clipboardHandler = ClipboardHandlerMac()

parseArgs()
if checkAdbDependency() is True:
    if clipboardHandler.checkDependencies() is True:
        syncWithDevices(clipboardHandler)
