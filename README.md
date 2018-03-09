# AdbClipboard #
https://github.com/PRosenb/AdbClipboard

AdbClipboard is a small app on your smartphone that allows you to read/write the Android clipboard using adb.

## Features ##
- Easy to use
- Very small app
- Does not request any permissions
- Python script on your PC to communicate with the app over adb (USB cable or Wifi for rooted devices)

## Installation ##
There are two parts to install: The app on your test phones and the python script on your development PC.

### AdbClipboard app ###
The app will be published on Google Play and needs to be built yourself until then.

### Python script ###
- [Download the latest version](https://github.com/PRosenb/AdbClipboard/releases/latest)
- Uncompress the downloaded file
- This will result in a folder containing all the files for the library. The folder name includes the version: **AdbClipboard-x.y.z**

#### Mac/Linux ####
   - Copy the file adbclipboard.py to e.g. your home directory:
```bash
cp ./adbclipboard.py ~/
```
   - make adbclipboard.py executable
```bash
cd
chmod +x ./adbclipboard.py
```
   - Start adbclipboard.py
```bash
cd
./adbclipboard.py
```

## Contributions ##
Enhancements and improvements are welcome.

## License ##
```
AdbClipboard
Copyright (c) 2018 Peter Rosenberg (https://github.com/PRosenb).

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
