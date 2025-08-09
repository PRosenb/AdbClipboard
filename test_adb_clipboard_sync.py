#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import subprocess
import unittest
from unittest.mock import Mock, patch
from typing import List, Optional

# Run Tests:
# pip install pytest
# pytest test_adb_clipboard_sync.py -v


# Import classes from the main script
# Assuming the main script is saved as 'adb_clipboard_sync.py'
try:
    from adb_clipboard_sync import (
        Config,
        Response, 
        ResponseStatus,
        CommandRunner,
        AdbManager,
        MacClipboardHandler,
        LinuxClipboardHandler,
        WindowsClipboardHandler,
        ClipboardSyncManager,
        create_clipboard_handler,
        setup_logging,
        parse_arguments
    )
except ImportError as e:
    print(f"Error importing from main script: {e}")
    print("Please make sure 'adb_clipboard_sync.py' is in the same directory as this test file")
    exit(1)


class TestCommandRunner(unittest.TestCase):
    
    def setUp(self):
        self.logger = Mock(spec=logging.Logger)
        self.runner = CommandRunner(self.logger)
    
    @patch('subprocess.run')
    def test_successful_command(self, mock_run):
        """Test successful command execution"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "success output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # When
        result = self.runner.run_command(['echo', 'test'], context="test command")
        
        # Then
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 0)
        mock_run.assert_called_once_with(
            ['echo', 'test'],
            capture_output=True,
            text=True,
            timeout=30,
            input=None
        )
        self.logger.debug.assert_called_once_with("Running test command: echo test")
        self.logger.warning.assert_not_called()
    
    @patch('subprocess.run')
    def test_failed_command(self, mock_run):
        """Test failed command execution"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error message"
        mock_run.return_value = mock_result
        
        # When
        result = self.runner.run_command(['false'], context="test command")
        
        # Then
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 1)
        self.logger.warning.assert_any_call("test command failed with return code: 1")
        self.logger.warning.assert_any_call("Error output: error message")
    
    @patch('subprocess.run')
    def test_expected_failure_not_logged(self, mock_run):
        """Test that expected failures are not logged as warnings"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "cat: /path/file: No such file or directory"
        mock_run.return_value = mock_result
        
        # When
        result = self.runner.run_command(['cat', '/path/file'], context="read from device test123")
        
        # Then
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 1)
        self.logger.debug.assert_called_once()
        self.logger.warning.assert_not_called()  # Should not log warnings for expected failures
    
    @patch('subprocess.run')
    def test_file_not_found_exception(self, mock_run):
        """Test FileNotFoundError handling"""
        # Given
        mock_run.side_effect = FileNotFoundError()
        
        # When
        result = self.runner.run_command(['nonexistent'], context="test command")
        
        # Then
        self.assertIsNone(result)
        self.logger.error.assert_called_once_with("test command not found: nonexistent")
    
    @patch('subprocess.run')
    def test_timeout_exception(self, mock_run):
        """Test timeout handling"""
        # Given
        mock_run.side_effect = subprocess.TimeoutExpired(['sleep', '10'], 5)
        
        # When
        result = self.runner.run_command(['sleep', '10'], timeout=5, context="test command")
        
        # Then
        self.assertIsNone(result)
        self.logger.error.assert_called_once_with("test command timed out after 5s")
    
    @patch('subprocess.run')
    def test_generic_exception(self, mock_run):
        """Test generic exception handling"""
        # Given
        mock_run.side_effect = RuntimeError("Something went wrong")
        
        # When
        result = self.runner.run_command(['test'], context="test command")
        
        # Then
        self.assertIsNone(result)
        self.logger.error.assert_called_once_with("Error running test command: Something went wrong")


class TestAdbManager(unittest.TestCase):
    
    def setUp(self):
        self.logger = Mock(spec=logging.Logger)
        self.runner_mock = Mock(spec=CommandRunner)
        self.adb_manager = AdbManager(self.runner_mock, self.logger)
    
    def test_check_dependency_success(self):
        """Test successful ADB dependency check"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 0
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        result = self.adb_manager.check_dependency()
        
        # Then
        self.assertTrue(result)
        self.runner_mock.run_command.assert_called_once_with(
            ['adb', 'version'], 10, None, "adb dependency check"
        )
    
    def test_check_dependency_failure(self):
        """Test failed ADB dependency check"""
        # Given
        self.runner_mock.run_command.return_value = None
        
        # When
        result = self.adb_manager.check_dependency()
        
        # Then
        self.assertFalse(result)
    
    def test_get_connected_devices_success(self):
        """Test getting connected devices successfully"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\ndevice1\tdevice\ndevice2\tdevice\ndevice3\toffline\n"
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        devices = self.adb_manager.get_connected_devices()
        
        # Then
        self.assertEqual(devices, ["device1", "device2"])  # offline device should be excluded
        self.runner_mock.run_command.assert_called_once_with(
            ['adb', 'devices'], 30, None, "adb devices"
        )
    
    def test_get_connected_devices_empty(self):
        """Test getting connected devices when none are connected"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\n"
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        devices = self.adb_manager.get_connected_devices()
        
        # Then
        self.assertEqual(devices, [])
    
    def test_get_connected_devices_failure(self):
        """Test getting connected devices when ADB command fails"""
        # Given
        self.runner_mock.run_command.return_value = None
        
        # When
        devices = self.adb_manager.get_connected_devices()
        
        # Then
        self.assertEqual(devices, [])
    
    def test_write_to_device_success(self):
        """Test successful write to device"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Broadcasting: Intent { ... }\nBroadcast completed: result=-1"
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        response = self.adb_manager.write_to_device("device123", "test text")
        
        # Then
        self.assertEqual(response.status, ResponseStatus.SUCCESS)
        expected_cmd = [
            'adb', '-s', 'device123', 'shell', 'am', 'broadcast',
            '-n', 'ch.pete.adbclipboard/.WriteReceiver',
            '-e', 'text', 'test+text'
        ]
        self.runner_mock.run_command.assert_called_once_with(
            expected_cmd, 30, None, "write to device device123"
        )
    
    def test_write_to_device_failure(self):
        """Test failed write to device"""
        # Given
        self.runner_mock.run_command.return_value = None
        
        # When
        response = self.adb_manager.write_to_device("device123", "test text")
        
        # Then
        self.assertEqual(response.status, ResponseStatus.ERROR)
        self.assertEqual(response.data, "")
    
    def test_read_from_device_success(self):
        """Test successful read from device"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "clipboard content from device"
        mock_result.stderr = ""
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        response = self.adb_manager.read_from_device("device123")
        
        # Then
        self.assertEqual(response.status, ResponseStatus.SUCCESS)
        self.assertEqual(response.data, "clipboard content from device")
    
    def test_read_from_device_file_not_found(self):
        """Test read from device when file doesn't exist"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "cat: /path/clipboard.txt: No such file or directory"
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        response = self.adb_manager.read_from_device("device123")
        
        # Then
        self.assertEqual(response.status, ResponseStatus.SUCCESS)
        self.assertEqual(response.data, "")
    
    def test_read_from_device_other_error(self):
        """Test read from device with other error"""
        # Given
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "permission denied"
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        response = self.adb_manager.read_from_device("device123")
        
        # Then
        self.assertEqual(response.status, ResponseStatus.ERROR)
        self.assertEqual(response.data, "")
    
    def test_parse_broadcast_response_success(self):
        """Test parsing successful broadcast response"""
        # Given
        response_text = "Broadcasting: Intent { ... }\nBroadcast completed: result=-1, data=\"response data\""
        
        # When
        response = self.adb_manager._parse_broadcast_response(response_text)
        
        # Then
        self.assertEqual(response.status, ResponseStatus.SUCCESS)
        self.assertEqual(response.data, "response data")
    
    def test_parse_broadcast_response_error(self):
        """Test parsing error broadcast response"""
        # Given
        response_text = "Broadcasting: Intent { ... }\nBroadcast completed: result=1"
        
        # When
        response = self.adb_manager._parse_broadcast_response(response_text)
        
        # Then
        self.assertEqual(response.status, ResponseStatus.ERROR)


class TestClipboardHandlers(unittest.TestCase):
    
    def setUp(self):
        self.logger = Mock(spec=logging.Logger)
        self.runner_mock = Mock(spec=CommandRunner)
    
    def test_mac_clipboard_handler_read(self):
        """Test MacClipboardHandler read functionality"""
        # Given
        handler = MacClipboardHandler(self.runner_mock)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "clipboard content"
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        result = handler.read_clipboard()
        
        # Then
        self.assertEqual(result, "clipboard content")
        self.runner_mock.run_command.assert_called_once_with(['pbpaste'], context="pbpaste")
    
    def test_mac_clipboard_handler_write(self):
        """Test MacClipboardHandler write functionality"""
        # Given
        handler = MacClipboardHandler(self.runner_mock)
        
        # When
        handler.write_clipboard("test content")
        
        # Then
        self.runner_mock.run_command.assert_called_once_with(
            ['pbcopy'], input_text="test content", context="pbcopy"
        )
    
    def test_linux_clipboard_handler_dependencies(self):
        """Test LinuxClipboardHandler dependency check"""
        # Given
        handler = LinuxClipboardHandler(self.runner_mock)
        mock_result = Mock()
        mock_result.returncode = 0
        self.runner_mock.run_command.return_value = mock_result
        
        # When
        result = handler.check_dependencies()
        
        # Then
        self.assertTrue(result)
        self.runner_mock.run_command.assert_called_once_with(
            ['xclip', '-version'], context="xclip check"
        )
    
    @patch('platform.system')
    def test_create_clipboard_handler_mac(self, mock_system):
        """Test creating clipboard handler for Mac"""
        # Given
        mock_system.return_value = "Darwin"
        runner_mock = Mock()
        
        # When
        handler = create_clipboard_handler(runner_mock)
        
        # Then
        self.assertIsInstance(handler, MacClipboardHandler)
    
    @patch('platform.system')
    def test_create_clipboard_handler_linux(self, mock_system):
        """Test creating clipboard handler for Linux"""
        # Given
        mock_system.return_value = "Linux"
        runner_mock = Mock()
        
        # When
        handler = create_clipboard_handler(runner_mock)
        
        # Then
        self.assertIsInstance(handler, LinuxClipboardHandler)
    
    @patch('platform.system')
    def test_create_clipboard_handler_windows(self, mock_system):
        """Test creating clipboard handler for Windows"""
        # Given
        mock_system.return_value = "Windows"
        runner_mock = Mock()
        
        # When
        handler = create_clipboard_handler(runner_mock)
        
        # Then
        self.assertIsInstance(handler, WindowsClipboardHandler)
    
    @patch('platform.system')
    def test_create_clipboard_handler_unsupported(self, mock_system):
        """Test creating clipboard handler for unsupported platform"""
        # Given
        mock_system.return_value = "UnsupportedOS"
        runner_mock = Mock()
        
        # When/Then
        with self.assertRaises(RuntimeError):
            create_clipboard_handler(runner_mock)


class TestClipboardSyncManager(unittest.TestCase):
    
    def setUp(self):
        self.config = Config(verbose=True, connected_devices_delay=1, no_connected_device_delay=2)
        self.logger = Mock(spec=logging.Logger)
        self.clipboard_handler = Mock()
        self.adb_manager = Mock()
        self.sync_manager = ClipboardSyncManager(
            self.config, self.clipboard_handler, self.adb_manager, self.logger
        )
    
    def test_sync_clipboard_to_devices_success(self):
        """Test syncing clipboard to devices when content changes"""
        # Given
        self.clipboard_handler.read_clipboard.return_value = "new content"
        self.sync_manager.previous_clipboard = "old content"
        success_response = Response(ResponseStatus.SUCCESS, "")
        self.adb_manager.write_to_device.return_value = success_response
        
        # When
        result = self.sync_manager._sync_clipboard_to_devices(["device1", "device2"])
        
        # Then
        self.assertTrue(result)
        self.assertEqual(self.adb_manager.write_to_device.call_count, 2)
        self.adb_manager.write_to_device.assert_any_call("device1", "new content")
        self.adb_manager.write_to_device.assert_any_call("device2", "new content")
    
    def test_sync_clipboard_to_devices_no_change(self):
        """Test syncing clipboard to devices when content hasn't changed"""
        # Given
        self.clipboard_handler.read_clipboard.return_value = "same content"
        self.sync_manager.previous_clipboard = "same content"
        
        # When
        result = self.sync_manager._sync_clipboard_to_devices(["device1"])
        
        # Then
        self.assertFalse(result)
        self.adb_manager.write_to_device.assert_not_called()
    
    def test_sync_clipboard_from_devices_success(self):
        """Test syncing clipboard from devices when device has new content"""
        # Given
        self.clipboard_handler.read_clipboard.return_value = "desktop content"
        device_response = Response(ResponseStatus.SUCCESS, "device content")
        self.adb_manager.read_from_device.return_value = device_response
        
        # When
        result = self.sync_manager._sync_clipboard_from_devices(["device1"])
        
        # Then
        self.assertTrue(result)
        self.clipboard_handler.write_clipboard.assert_called_once_with("device content")
        self.assertEqual(self.sync_manager.previous_clipboard, "device content")
    
    def test_sync_clipboard_from_devices_no_change(self):
        """Test syncing clipboard from devices when content is same"""
        # Given
        self.clipboard_handler.read_clipboard.return_value = "same content"
        device_response = Response(ResponseStatus.SUCCESS, "same content")
        self.adb_manager.read_from_device.return_value = device_response
        
        # When
        result = self.sync_manager._sync_clipboard_from_devices(["device1"])
        
        # Then
        self.assertFalse(result)
        self.clipboard_handler.write_clipboard.assert_not_called()


class TestConfiguration(unittest.TestCase):
    
    def test_config_defaults(self):
        """Test Config default values"""
        # Given/When
        config = Config()
        
        # Then
        self.assertFalse(config.verbose)
        self.assertEqual(config.connected_devices_delay, 5)
        self.assertEqual(config.no_connected_device_delay, 60)
        self.assertIsNone(config.log_file)
    
    def test_config_custom_values(self):
        """Test Config with custom values"""
        # Given/When
        config = Config(
            verbose=True, 
            connected_devices_delay=3, 
            no_connected_device_delay=30, 
            log_file="test.log"
        )
        
        # Then
        self.assertTrue(config.verbose)
        self.assertEqual(config.connected_devices_delay, 3)
        self.assertEqual(config.no_connected_device_delay, 30)
        self.assertEqual(config.log_file, "test.log")
    
    @patch('sys.argv', ['script.py', '-v', '-c', '3', '-n', '30', '--log-file', 'test.log'])
    def test_parse_arguments(self):
        """Test command line argument parsing"""
        # Given - sys.argv is patched above
        
        # When
        config = parse_arguments()
        
        # Then
        self.assertTrue(config.verbose)
        self.assertEqual(config.connected_devices_delay, 3)
        self.assertEqual(config.no_connected_device_delay, 30)
        self.assertEqual(config.log_file, "test.log")


class TestResponse(unittest.TestCase):
    
    def test_response_default(self):
        """Test Response default values"""
        # Given/When
        response = Response()
        
        # Then
        self.assertEqual(response.status, ResponseStatus.ERROR)
        self.assertEqual(response.data, "")
    
    def test_response_custom_values(self):
        """Test Response with custom values"""
        # Given/When
        response = Response(ResponseStatus.SUCCESS, "test data")
        
        # Then
        self.assertEqual(response.status, ResponseStatus.SUCCESS)
        self.assertEqual(response.data, "test data")


class TestLogging(unittest.TestCase):
    
    def test_setup_logging_basic(self):
        """Test basic logging setup"""
        # Given
        config = Config(verbose=False)
        
        # When
        logger = setup_logging(config)
        
        # Then
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'adb_clipboard_sync')
    
    def test_setup_logging_verbose(self):
        """Test verbose logging setup"""
        # Given
        config = Config(verbose=True)
        
        # When
        logger = setup_logging(config)
        
        # Then
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.level, logging.DEBUG)


if __name__ == '__main__':
    unittest.main(verbosity=2)