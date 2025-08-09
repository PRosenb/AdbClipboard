#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import platform
import re
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional
from urllib import parse

# Constants
CONNECTED_DEVICES_DELAY_DEFAULT = 5
NO_CONNECTED_DEVICE_DELAY_DEFAULT = 60
DEFAULT_TIMEOUT = 30
ADB_CLIPBOARD_PACKAGE = 'ch.pete.adbclipboard'
CLIPBOARD_FILE_PATH = f'/sdcard/Android/data/{ADB_CLIPBOARD_PACKAGE}/files/clipboard.txt'


class ResponseStatus(Enum):
    """Response status for ADB operations"""
    SUCCESS = -1  # ADB broadcast returns -1 for success
    ERROR = 1


@dataclass
class Response:
    """Response object for ADB operations"""
    status: ResponseStatus = ResponseStatus.ERROR
    data: str = ""


@dataclass
class Config:
    """Configuration settings for the clipboard sync"""
    verbose: bool = False
    connected_devices_delay: int = CONNECTED_DEVICES_DELAY_DEFAULT
    no_connected_device_delay: int = NO_CONNECTED_DEVICE_DELAY_DEFAULT
    log_file: Optional[str] = None


class ClipboardHandler(ABC):
    """Abstract base class for platform-specific clipboard handlers"""
    
    @abstractmethod
    def check_dependencies(self) -> bool:
        """Check if required dependencies are available"""
        pass
    
    @abstractmethod
    def read_clipboard(self) -> str:
        """Read text from clipboard"""
        pass
    
    @abstractmethod
    def write_clipboard(self, text: str) -> None:
        """Write text to clipboard"""
        pass


class CommandRunner:
    """Centralized command runner with consistent error handling"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def run_command(self, cmd: List[str], timeout: int = DEFAULT_TIMEOUT, 
                   input_text: Optional[str] = None, context: str = "command") -> Optional[subprocess.CompletedProcess]:
        """
        Run external command with consistent error handling
        
        Args:
            cmd: List of command arguments
            timeout: Timeout in seconds
            input_text: Text to send to stdin
            context: Description for logging
            
        Returns:
            CompletedProcess object or None if failed
        """
        try:
            self.logger.debug(f"Running {context}: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_text
            )
            
            # Only log warnings for actual errors, not expected failures
            if result.returncode != 0 and not self._is_expected_failure(context, result):
                self.logger.warning(f"{context} failed with return code: {result.returncode}")
                if result.stderr:
                    self.logger.warning(f"Error output: {result.stderr.strip()}")
            
            return result
            
        except FileNotFoundError:
            self.logger.error(f"{context} not found: {cmd[0]}")
            return None
        except subprocess.TimeoutExpired:
            self.logger.error(f"{context} timed out after {timeout}s")
            return None
        except Exception as e:
            self.logger.error(f"Error running {context}: {e}")
            return None
    
    def _is_expected_failure(self, context: str, result: subprocess.CompletedProcess) -> bool:
        """Check if a command failure is expected and should not be logged as warning"""
        # Reading clipboard file when it doesn't exist is expected
        if "read from device" in context and result.stderr and "No such file or directory" in result.stderr:
            return True
        return False


class AdbManager:
    """Manager for ADB operations"""
    
    def __init__(self, command_runner: CommandRunner, logger: logging.Logger):
        self.runner = command_runner
        self.logger = logger
    
    def run_adb_command(self, args: List[str], timeout: int = DEFAULT_TIMEOUT, 
                       input_text: Optional[str] = None, context: str = "adb command") -> Optional[subprocess.CompletedProcess]:
        """Run ADB command"""
        cmd = ['adb'] + args
        return self.runner.run_command(cmd, timeout, input_text, context)
    
    def check_dependency(self) -> bool:
        """Check if ADB is available"""
        result = self.run_adb_command(['version'], timeout=10, context="adb dependency check")
        return result is not None and result.returncode == 0
    
    def get_connected_devices(self) -> List[str]:
        """Get list of connected device hashes"""
        result = self.run_adb_command(['devices'], context="adb devices")
        if result is None or result.returncode != 0:
            return []
        
        lines = result.stdout.strip().split('\n')[1:]  # Skip header line
        devices = []
        
        for line in lines:
            if line.strip() and '\t' in line:
                device_hash = line.split('\t')[0]
                status = line.split('\t')[1]
                if status == 'device':  # Only include properly connected devices
                    devices.append(device_hash)
        
        return devices
    
    def write_to_device(self, device_hash: str, text: str) -> Response:
        """Write text to device clipboard"""
        url_encoded_text = parse.quote_plus(text)
        
        result = self.run_adb_command([
            '-s', device_hash,
            'shell', 'am', 'broadcast',
            '-n', f'{ADB_CLIPBOARD_PACKAGE}/.WriteReceiver',
            '-e', 'text', url_encoded_text
        ], context=f"write to device {device_hash}")
        
        if result is None or result.returncode != 0:
            return Response(ResponseStatus.ERROR, "")
        
        self.logger.debug(f"Write response from {device_hash}: {result.stdout}")
        return self._parse_broadcast_response(result.stdout)
    
    def read_from_device(self, device_hash: str) -> Response:
        """Read text from device clipboard"""
        # Try to read the clipboard file
        result = self.run_adb_command([
            '-s', device_hash, 'shell', 'cat', CLIPBOARD_FILE_PATH
        ], context=f"read from device {device_hash}")
        
        if result is None:
            return Response(ResponseStatus.ERROR, "")
        
        # Check if file doesn't exist (expected when no clipboard changes)
        if result.returncode != 0 and result.stderr and "No such file or directory" in result.stderr:
            # This is expected behavior - don't log as error
            return Response(ResponseStatus.SUCCESS, "")
        
        if result.returncode != 0:
            # This is an actual error
            return Response(ResponseStatus.ERROR, "")
        
        content = result.stdout.strip()
        
        # Clean up the file after successful read
        if content:
            self._cleanup_device_file(device_hash)
            self.logger.info(f"Read from {device_hash}: {content}")
        
        return Response(ResponseStatus.SUCCESS, content)
    
    def _cleanup_device_file(self, device_hash: str) -> None:
        """Remove clipboard file from device after reading"""
        result = self.run_adb_command([
            '-s', device_hash, 'shell', 'rm', CLIPBOARD_FILE_PATH
        ], timeout=10, context=f"cleanup device {device_hash}")
        
        if result:
            self.logger.debug(f"Cleanup response: stdout={result.stdout}, stderr={result.stderr}")
    
    def _parse_broadcast_response(self, response_text: str) -> Response:
        """Parse ADB broadcast response"""
        result_pattern = re.compile(r".*\n.*result=([-]?\d*).*")
        match = result_pattern.match(response_text)
        
        response = Response()
        
        if match and match.group(1):
            status_value = int(match.group(1))
            response.status = ResponseStatus.SUCCESS if status_value == -1 else ResponseStatus.ERROR
            
            if response.status == ResponseStatus.SUCCESS:
                # Extract data if present
                data_pattern = re.compile(r'.*\n.*data="(.*)"$', re.DOTALL)
                data_match = data_pattern.match(response_text)
                if data_match:
                    response.data = data_match.group(1)
        
        return response


class MacClipboardHandler(ClipboardHandler):
    """macOS clipboard handler using pbcopy/pbpaste"""
    
    def __init__(self, command_runner: CommandRunner):
        self.runner = command_runner
    
    def check_dependencies(self) -> bool:
        """pbcopy/pbpaste are built into macOS"""
        return True
    
    def read_clipboard(self) -> str:
        """Read from macOS clipboard"""
        result = self.runner.run_command(['pbpaste'], context="pbpaste")
        return result.stdout if result and result.returncode == 0 else ""
    
    def write_clipboard(self, text: str) -> None:
        """Write to macOS clipboard"""
        self.runner.run_command(['pbcopy'], input_text=text, context="pbcopy")


class LinuxClipboardHandler(ClipboardHandler):
    """Linux clipboard handler using xclip"""
    
    def __init__(self, command_runner: CommandRunner):
        self.runner = command_runner
    
    def check_dependencies(self) -> bool:
        """Check if xclip is available"""
        result = self.runner.run_command(['xclip', '-version'], context="xclip check")
        return result is not None and result.returncode == 0
    
    def read_clipboard(self) -> str:
        """Read from X11 clipboard"""
        result = self.runner.run_command(['xclip', '-selection', 'clipboard', '-o'], context="xclip read")
        return result.stdout if result and result.returncode == 0 else ""
    
    def write_clipboard(self, text: str) -> None:
        """Write to X11 clipboard"""
        self.runner.run_command(['xclip', '-selection', 'clipboard'], input_text=text, context="xclip write")


class WindowsClipboardHandler(ClipboardHandler):
    """Windows clipboard handler using PowerShell"""
    
    def __init__(self, command_runner: CommandRunner):
        self.runner = command_runner
    
    def check_dependencies(self) -> bool:
        """PowerShell is available on modern Windows"""
        result = self.runner.run_command(['powershell', '-Command', 'echo test'], context="powershell check")
        return result is not None and result.returncode == 0
    
    def read_clipboard(self) -> str:
        """Read from Windows clipboard"""
        result = self.runner.run_command([
            'powershell', '-Command', 'Get-Clipboard'
        ], context="powershell read clipboard")
        return result.stdout.rstrip('\r\n') if result and result.returncode == 0 else ""
    
    def write_clipboard(self, text: str) -> None:
        """Write to Windows clipboard"""
        self.runner.run_command([
            'powershell', '-Command', f'Set-Clipboard -Value "{text}"'
        ], context="powershell write clipboard")


class ClipboardSyncManager:
    """Main clipboard synchronization manager"""
    
    def __init__(self, config: Config, clipboard_handler: ClipboardHandler, 
                 adb_manager: AdbManager, logger: logging.Logger):
        self.config = config
        self.clipboard_handler = clipboard_handler
        self.adb_manager = adb_manager
        self.logger = logger
        self.previous_clipboard = None
    
    def sync_with_devices(self) -> None:
        """Main sync loop"""
        self.logger.info("Starting clipboard sync...")
        
        while True:
            try:
                devices = self.adb_manager.get_connected_devices()
                
                if not devices:
                    self._handle_no_devices()
                    continue
                
                if self._sync_clipboard_to_devices(devices):
                    continue
                
                if self._sync_clipboard_from_devices(devices):
                    continue
                
                time.sleep(self.config.connected_devices_delay)
                
            except KeyboardInterrupt:
                self.logger.info("Sync interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in sync loop: {e}")
                time.sleep(self.config.connected_devices_delay)
    
    def _handle_no_devices(self) -> None:
        """Handle case when no devices are connected"""
        self.logger.info(f"No devices connected, sleeping for {self.config.no_connected_device_delay}s")
        self.previous_clipboard = None
        time.sleep(self.config.no_connected_device_delay)
    
    def _sync_clipboard_to_devices(self, devices: List[str]) -> bool:
        """Sync desktop clipboard to devices"""
        current_clipboard = self.clipboard_handler.read_clipboard()
        
        if self.previous_clipboard != current_clipboard and current_clipboard:
            self.previous_clipboard = current_clipboard
            has_compatible_device = False
            
            for device in devices:
                response = self.adb_manager.write_to_device(device, current_clipboard)
                status = " (success)" if response.status == ResponseStatus.SUCCESS else " (failed)"
                
                if response.status == ResponseStatus.SUCCESS:
                    has_compatible_device = True
                
                self.logger.info(f"Write to {device}: {current_clipboard[:50]}{'...' if len(current_clipboard) > 50 else ''}{status}")
            
            if not has_compatible_device:
                self._handle_no_compatible_devices()
            
            return True
        
        return False
    
    def _sync_clipboard_from_devices(self, devices: List[str]) -> bool:
        """Sync device clipboard to desktop"""
        desktop_clipboard = self.clipboard_handler.read_clipboard()
        has_compatible_device = False
        
        for device in devices:
            response = self.adb_manager.read_from_device(device)
            
            if response.status == ResponseStatus.SUCCESS:
                has_compatible_device = True
                device_text = response.data
                
                if device_text and device_text != desktop_clipboard:
                    self.logger.info(f"Updating desktop clipboard from {device}: {device_text}")
                    self.clipboard_handler.write_clipboard(device_text)
                    self.previous_clipboard = device_text
                    return True
        
        if not has_compatible_device:
            self._handle_no_compatible_devices()
        
        return False
    
    def _handle_no_compatible_devices(self) -> None:
        """Handle case when no devices have ADB Clipboard installed"""
        self.logger.warning(f"No devices with AdbClipboard app installed found, sleeping for {self.config.no_connected_device_delay}s")
        self.logger.info("Please install AdbClipboard from: https://play.google.com/store/apps/details?id=ch.pete.adbclipboard")
        self.previous_clipboard = None
        time.sleep(self.config.no_connected_device_delay)


def setup_logging(config: Config) -> logging.Logger:
    """Setup logging configuration"""
    logger = logging.getLogger('adb_clipboard_sync')
    logger.setLevel(logging.DEBUG if config.verbose else logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if config.verbose else logging.INFO)
    
    # File handler if specified
    handlers = [console_handler]
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setLevel(logging.DEBUG)
        handlers.append(file_handler)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def create_clipboard_handler(command_runner: CommandRunner) -> ClipboardHandler:
    """Create appropriate clipboard handler for current platform"""
    system = platform.system()
    
    if system == "Darwin":
        return MacClipboardHandler(command_runner)
    elif system == "Linux":
        return LinuxClipboardHandler(command_runner)
    elif system == "Windows":
        return WindowsClipboardHandler(command_runner)
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def parse_arguments() -> Config:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Sync clipboard with connected Android devices via ADB.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run with default settings
  %(prog)s -v                        # Run with verbose output
  %(prog)s -c 3 -n 30               # Custom delays
  %(prog)s --log-file sync.log       # Log to file
        """)
    
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output and debug logging')
    parser.add_argument('-c', '--connected-devices-delay', type=int, default=CONNECTED_DEVICES_DELAY_DEFAULT,
                        help=f'Delay between syncs when devices are connected (default: {CONNECTED_DEVICES_DELAY_DEFAULT}s)')
    parser.add_argument('-n', '--no-connected-device-delay', type=int, default=NO_CONNECTED_DEVICE_DELAY_DEFAULT,
                        help=f'Delay between checks when no devices connected (default: {NO_CONNECTED_DEVICE_DELAY_DEFAULT}s)')
    parser.add_argument('--log-file', type=str,
                        help='Log to specified file in addition to console')
    
    args = parser.parse_args()
    
    return Config(
        verbose=args.verbose,
        connected_devices_delay=args.connected_devices_delay,
        no_connected_device_delay=args.no_connected_device_delay,
        log_file=args.log_file
    )


def main():
    """Main entry point"""
    try:
        config = parse_arguments()
        logger = setup_logging(config)
        
        # Initialize components
        command_runner = CommandRunner(logger)
        adb_manager = AdbManager(command_runner, logger)
        clipboard_handler = create_clipboard_handler(command_runner)
        
        # Check dependencies
        if not adb_manager.check_dependency():
            logger.error("ADB not found. Please install Android SDK platform tools.")
            sys.exit(1)
        
        if not clipboard_handler.check_dependencies():
            logger.error("Required clipboard dependencies not found.")
            sys.exit(1)
        
        # Start sync
        sync_manager = ClipboardSyncManager(config, clipboard_handler, adb_manager, logger)
        sync_manager.sync_with_devices()
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()