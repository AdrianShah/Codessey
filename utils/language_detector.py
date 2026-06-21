"""Language detection for submitted code files."""

import os
from typing import Literal

SUPPORTED_LANGUAGES = Literal[
    "python", "javascript", "typescript", "java", "go", "cpp", "unknown"
]

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
}

# Simple heuristic keywords for content-based detection
LANGUAGE_HINTS: dict[str, list[str]] = {
    "python": ["def ", "import ", "from ", "class ", "self.", "elif "],
    "javascript": ["function ", "const ", "let ", "var ", "=>", "require("],
    "typescript": ["interface ", "type ", ": string", ": number", "export "],
    "java": ["public class", "public static", "System.out", "import java."],
    "go": ["func ", "package ", "import (", "fmt.", "go func"],
    "cpp": ["#include", "std::", "int main(", "cout <<", "nullptr"],
}


def detect_language(filename: str | None, content: str) -> tuple[str, float]:
    """Detect programming language. Returns (language, confidence 0.0-1.0)."""
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in EXTENSION_MAP:
            return EXTENSION_MAP[ext], 0.95

    # Content-based heuristic
    scores: dict[str, int] = {}
    for lang, hints in LANGUAGE_HINTS.items():
        scores[lang] = sum(1 for h in hints if h in content)

    if not scores or max(scores.values()) == 0:
        return "unknown", 0.0

    best_lang = max(scores, key=scores.get)  # type: ignore[arg-type]
    confidence = min(scores[best_lang] / 3.0, 1.0)
    return best_lang, confidence
