"""Tests for ingestion and input validation."""

import pytest
from security.input_sanitizer import validate_file_upload, validate_paste, InputValidationError
from security.url_validator import validate_github_url, URLValidationError
from utils.language_detector import detect_language
from utils.code_chunker import chunk_code


class TestInputSanitizer:
    def test_empty_paste_rejected(self):
        with pytest.raises(InputValidationError, match="No code detected"):
            validate_paste("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(InputValidationError, match="No code detected"):
            validate_paste("   \n\n\t  ")

    def test_oversized_paste_rejected(self):
        big = "x" * (3 * 1024 * 1024)
        with pytest.raises(InputValidationError, match="size limit"):
            validate_paste(big)

    def test_valid_paste_accepted(self):
        result = validate_paste("def hello(): pass")
        assert result == "def hello(): pass"

    def test_binary_file_rejected(self):
        binary_content = b"\x00\x01\x02\x03" * 100
        with pytest.raises(InputValidationError, match="binary"):
            validate_file_upload("test.py", binary_content)

    def test_unsupported_extension_rejected(self):
        with pytest.raises(InputValidationError, match="Unsupported"):
            validate_file_upload("test.pdf", b"some content")

    def test_valid_file_accepted(self):
        result = validate_file_upload("test.py", b"def hello(): pass")
        assert result == "def hello(): pass"


class TestURLValidator:
    def test_valid_github_url(self):
        url = "https://github.com/user/repo/blob/main/file.py"
        assert validate_github_url(url) == url

    def test_http_rejected(self):
        with pytest.raises(URLValidationError, match="HTTPS"):
            validate_github_url("http://github.com/user/repo/blob/main/file.py")

    def test_ssrf_ip_rejected(self):
        with pytest.raises(URLValidationError):
            validate_github_url("https://169.254.169.254/latest/meta-data")

    def test_evil_domain_rejected(self):
        with pytest.raises(URLValidationError):
            validate_github_url("https://github.com.evil.com/x/y/blob/main/f.py")

    def test_directory_url_rejected(self):
        with pytest.raises(URLValidationError):
            validate_github_url("https://github.com/user/repo")


class TestLanguageDetector:
    def test_python_by_extension(self):
        lang, conf = detect_language("test.py", "")
        assert lang == "python"
        assert conf > 0.9

    def test_unknown_on_ambiguous(self):
        lang, conf = detect_language(None, "hello world")
        assert lang == "unknown"

    def test_javascript_by_content(self):
        lang, conf = detect_language(None, "const x = 5;\nfunction foo() {}")
        assert lang == "javascript"


class TestChunker:
    def test_small_file_single_chunk(self):
        content = "def foo():\n    pass\n"
        chunks = chunk_code(content, "test.py", "python")
        assert len(chunks) == 1
        assert chunks[0].line_start == 1

    def test_large_file_multiple_chunks(self):
        content = "\n".join(f"line {i}" for i in range(600))
        chunks = chunk_code(content, "big.py", "python")
        assert len(chunks) > 1
        # Check overlap exists
        assert chunks[1].line_start < chunks[0].line_end

    def test_filename_sanitized(self):
        from schemas.code_chunk import CodeChunk, ChunkMetadata
        with pytest.raises(Exception, match="path traversal"):
            CodeChunk(
                chunk_id="test",
                language="python",
                filename="../../etc/passwd",
                line_start=1,
                line_end=1,
                content="x = 1",
                metadata=ChunkMetadata(total_lines=1, functions=[], imports=[]),
            )
