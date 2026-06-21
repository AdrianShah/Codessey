"""Edge case tests — maps to PRD Section 7."""

import pytest
from security.input_sanitizer import validate_file_upload, validate_paste, InputValidationError
from utils.code_chunker import chunk_code


class TestEdgeCases:
    def test_ec01_empty_file(self):
        with pytest.raises(InputValidationError, match="No code detected"):
            validate_paste("")

    def test_ec02_whitespace_only(self):
        with pytest.raises(InputValidationError, match="No code detected"):
            validate_paste("   \n   \n   ")

    def test_ec03_oversized_file(self):
        big = "x\n" * 6000
        with pytest.raises(InputValidationError, match="5000 lines"):
            validate_paste(big)

    def test_ec04_binary_as_py(self):
        with pytest.raises(InputValidationError, match="binary"):
            validate_file_upload("malware.py", b"\x00\x89PNG\r\n" * 100)

    def test_ec06_single_long_line(self):
        # Single 10,000-char minified line should still work
        content = "var x=" + "a" * 9990 + ";"
        result = validate_paste(content)
        assert len(result) > 9000

    def test_chunker_handles_large_file(self):
        content = "\n".join(f"line {i}" for i in range(600))
        chunks = chunk_code(content, "big.py", "python")
        assert len(chunks) == 2
        # Verify no content lost
        all_lines = set()
        for chunk in chunks:
            for line in chunk.content.splitlines():
                all_lines.add(line)
        assert "line 0" in all_lines
        assert "line 599" in all_lines
