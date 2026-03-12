#!/usr/bin/env python3
"""Unit tests for swap_usage_delta.py"""

import json
import os
import tempfile
import unittest
from io import StringIO
from unittest.mock import mock_open, patch

import swap_usage_delta as sud


class TestParseMeminfo(unittest.TestCase):
    """Tests for parse_meminfo function."""

    def test_parse_valid_meminfo(self):
        """Test parsing valid /proc/meminfo content."""
        meminfo_content = """MemTotal:       16384000 kB
MemFree:         2048000 kB
SwapTotal:       8388608 kB
SwapFree:        7098860 kB
SwapCached:       524288 kB
"""
        with patch("builtins.open", mock_open(read_data=meminfo_content)):
            with patch.object(sud, "PROC_MEMINFO", "/proc/meminfo"):
                result = sud.parse_meminfo()

        self.assertEqual(result["total_kb"], 8388608)
        self.assertEqual(result["free_kb"], 7098860)
        self.assertEqual(result["cached_kb"], 524288)
        self.assertEqual(result["used_kb"], 8388608 - 7098860)

    def test_parse_meminfo_no_cached(self):
        """Test parsing meminfo without SwapCached."""
        meminfo_content = """SwapTotal:       4194304 kB
SwapFree:        3145728 kB
"""
        with patch("builtins.open", mock_open(read_data=meminfo_content)):
            with patch.object(sud, "PROC_MEMINFO", "/proc/meminfo"):
                result = sud.parse_meminfo()

        self.assertEqual(result["total_kb"], 4194304)
        self.assertEqual(result["free_kb"], 3145728)
        self.assertEqual(result["used_kb"], 4194304 - 3145728)
        self.assertNotIn("cached_kb", result)

    def test_parse_meminfo_whitespace_variations(self):
        """Test parsing with various whitespace formats."""
        meminfo_content = """SwapTotal:  8388608 kB
SwapFree: 7098860 kB
"""
        with patch("builtins.open", mock_open(read_data=meminfo_content)):
            with patch.object(sud, "PROC_MEMINFO", "/proc/meminfo"):
                result = sud.parse_meminfo()

        self.assertEqual(result["total_kb"], 8388608)
        self.assertEqual(result["free_kb"], 7098860)

    def test_parse_meminfo_file_not_found(self):
        """Test handling of missing /proc/meminfo."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch.object(sud, "PROC_MEMINFO", "/proc/meminfo"):
                with self.assertRaises(SystemExit):
                    sud.parse_meminfo()

    def test_parse_meminfo_permission_denied(self):
        """Test handling of permission errors."""
        with patch("builtins.open", side_effect=PermissionError):
            with patch.object(sud, "PROC_MEMINFO", "/proc/meminfo"):
                with self.assertRaises(SystemExit):
                    sud.parse_meminfo()

    def test_parse_meminfo_missing_required_fields(self):
        """Test handling when SwapTotal or SwapFree is missing."""
        meminfo_content = """MemTotal:       16384000 kB
MemFree:         2048000 kB
"""
        with patch("builtins.open", mock_open(read_data=meminfo_content)):
            with patch.object(sud, "PROC_MEMINFO", "/proc/meminfo"):
                with self.assertRaises(SystemExit):
                    sud.parse_meminfo()

    def test_parse_meminfo_malformed_lines(self):
        """Test handling of malformed lines in meminfo."""
        meminfo_content = """SwapTotal: 8388608 kB
InvalidLine
:
SwapFree: 7098860 kB
"""
        with patch("builtins.open", mock_open(read_data=meminfo_content)):
            with patch.object(sud, "PROC_MEMINFO", "/proc/meminfo"):
                result = sud.parse_meminfo()

        self.assertEqual(result["total_kb"], 8388608)
        self.assertEqual(result["free_kb"], 7098860)


class TestFormatSize(unittest.TestCase):
    """Tests for format_size function."""

    def test_format_kilobytes(self):
        """Test formatting values less than 1 MB."""
        self.assertEqual(sud.format_size(512), "512 kB")
        self.assertEqual(sud.format_size(1023), "1023 kB")

    def test_format_megabytes(self):
        """Test formatting values in MB range."""
        self.assertEqual(sud.format_size(1024), "1.00 MB")
        self.assertEqual(sud.format_size(1536), "1.50 MB")
        self.assertEqual(sud.format_size(1048575), "1024.00 MB")

    def test_format_gigabytes(self):
        """Test formatting values in GB range."""
        self.assertEqual(sud.format_size(1048576), "1.00 GB")
        self.assertEqual(sud.format_size(8388608), "8.00 GB")
        self.assertEqual(sud.format_size(2147483648), "2048.00 GB")

    def test_format_zero(self):
        """Test formatting zero value."""
        self.assertEqual(sud.format_size(0), "0 kB")


class TestCalculateDelta(unittest.TestCase):
    """Tests for calculate_delta function."""

    def test_delta_no_previous(self):
        """Test delta calculation with no previous reading."""
        current = {
            "total_kb": 8388608,
            "used_kb": 1048576,
            "free_kb": 7340032,
            "cached_kb": 262144,
        }
        result = sud.calculate_delta(current, None)

        self.assertEqual(result["total_delta"], 0)
        self.assertEqual(result["used_delta"], 0)
        self.assertEqual(result["free_delta"], 0)
        self.assertEqual(result["cached_delta"], 0)

    def test_delta_usage_increase(self):
        """Test delta when swap usage increases."""
        current = {
            "total_kb": 8388608,
            "used_kb": 2097152,
            "free_kb": 6291456,
            "cached_kb": 524288,
        }
        previous = {
            "total_kb": 8388608,
            "used_kb": 1048576,
            "free_kb": 7340032,
            "cached_kb": 262144,
        }
        result = sud.calculate_delta(current, previous)

        self.assertEqual(result["total_delta"], 0)
        self.assertEqual(result["used_delta"], 1048576)
        self.assertEqual(result["free_delta"], -1048576)
        self.assertEqual(result["cached_delta"], 262144)

    def test_delta_usage_decrease(self):
        """Test delta when swap usage decreases."""
        current = {
            "total_kb": 8388608,
            "used_kb": 524288,
            "free_kb": 7864320,
            "cached_kb": 131072,
        }
        previous = {
            "total_kb": 8388608,
            "used_kb": 1048576,
            "free_kb": 7340032,
            "cached_kb": 262144,
        }
        result = sud.calculate_delta(current, previous)

        self.assertEqual(result["used_delta"], -524288)
        self.assertEqual(result["free_delta"], 524288)
        self.assertEqual(result["cached_delta"], -131072)

    def test_delta_no_cached_in_previous(self):
        """Test delta when previous reading has no cached value."""
        current = {
            "total_kb": 8388608,
            "used_kb": 1048576,
            "free_kb": 7340032,
            "cached_kb": 262144,
        }
        previous = {
            "total_kb": 8388608,
            "used_kb": 524288,
            "free_kb": 7864320,
        }
        result = sud.calculate_delta(current, previous)

        self.assertEqual(result["cached_delta"], 262144)


class TestLoadHistory(unittest.TestCase):
    """Tests for load_history function."""

    def test_load_history_existing_file(self):
        """Test loading history from existing file."""
        history_data = [
            {"timestamp": "2026-03-12T14:30:00", "used_kb": 1048576},
            {"timestamp": "2026-03-12T14:35:00", "used_kb": 1572864},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(history_data, f)
            temp_path = f.name

        try:
            result = sud.load_history(temp_path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["used_kb"], 1048576)
        finally:
            os.unlink(temp_path)

    def test_load_history_nonexistent_file(self):
        """Test loading from nonexistent file."""
        result = sud.load_history("/nonexistent/path/swap_history.json")
        self.assertEqual(result, [])

    def test_load_history_invalid_json(self):
        """Test loading from file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            temp_path = f.name

        try:
            result = sud.load_history(temp_path)
            self.assertEqual(result, [])
        finally:
            os.unlink(temp_path)


class TestSaveHistory(unittest.TestCase):
    """Tests for save_history function."""

    def test_save_history(self):
        """Test saving history to file."""
        history_data = [
            {"timestamp": "2026-03-12T14:30:00", "used_kb": 1048576},
            {"timestamp": "2026-03-12T14:35:00", "used_kb": 1572864},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            sud.save_history(temp_path, history_data)

            with open(temp_path, "r") as f:
                loaded = json.load(f)

            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["used_kb"], 1048576)
        finally:
            os.unlink(temp_path)


class TestDisplaySnapshot(unittest.TestCase):
    """Tests for display_snapshot function."""

    def test_display_snapshot_basic(self):
        """Test basic snapshot display."""
        swap_info = {
            "total_kb": 8388608,
            "used_kb": 1048576,
            "free_kb": 7340032,
            "cached_kb": 262144,
        }

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            sud.display_snapshot(swap_info)
            output = mock_stdout.getvalue()

        self.assertIn("Swap Total:", output)
        self.assertIn("Swap Used:", output)
        self.assertIn("Swap Free:", output)
        self.assertIn("Swap Cached:", output)

    def test_display_snapshot_with_delta(self):
        """Test snapshot display with delta."""
        swap_info = {
            "total_kb": 8388608,
            "used_kb": 1048576,
            "free_kb": 7340032,
        }
        delta = {
            "used_delta": 524288,
            "free_delta": -524288,
            "cached_delta": 0,
        }

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            sud.display_snapshot(swap_info, delta)
            output = mock_stdout.getvalue()

        self.assertIn("Delta from last reading", output)
        self.assertIn("Used change:", output)
        self.assertIn("+", output)


if __name__ == "__main__":
    unittest.main()
