"""Code chunker — split large files into overlapping segments (PRD FR-3)."""

import uuid
from schemas.code_chunk import CodeChunk, ChunkMetadata

CHUNK_SIZE_LINES = 500
OVERLAP_LINES = 20


def chunk_code(
    content: str,
    filename: str,
    language: str,
) -> list[CodeChunk]:
    """Split content into overlapping chunks. Small files return a single chunk."""
    lines = content.splitlines(keepends=True)
    total_lines = len(lines)

    if total_lines <= CHUNK_SIZE_LINES:
        return [_make_chunk(content, filename, language, 1, total_lines, total_lines)]

    chunks: list[CodeChunk] = []
    start = 0
    while start < total_lines:
        end = min(start + CHUNK_SIZE_LINES, total_lines)
        chunk_content = "".join(lines[start:end])
        chunks.append(
            _make_chunk(chunk_content, filename, language, start + 1, end, total_lines)
        )
        if end >= total_lines:
            break
        start = end - OVERLAP_LINES

    return chunks


def _make_chunk(
    content: str,
    filename: str,
    language: str,
    line_start: int,
    line_end: int,
    total_lines: int,
) -> CodeChunk:
    functions = _extract_function_names(content, language)
    imports = _extract_imports(content, language)
    return CodeChunk(
        chunk_id=str(uuid.uuid4()),
        language=language,  # type: ignore[arg-type]
        filename=filename,
        line_start=line_start,
        line_end=line_end,
        content=content,
        metadata=ChunkMetadata(
            total_lines=total_lines,
            functions=functions,
            imports=imports,
        ),
    )


def _extract_function_names(content: str, language: str) -> list[str]:
    """Simple regex-free function name extraction."""
    names: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if language == "python" and stripped.startswith("def "):
            name = stripped[4:].split("(")[0].strip()
            if name:
                names.append(name)
        elif language in ("javascript", "typescript") and "function " in stripped:
            parts = stripped.split("function ")[1].split("(")[0].strip()
            if parts:
                names.append(parts)
        elif language == "go" and stripped.startswith("func "):
            name = stripped[5:].split("(")[0].strip()
            if name:
                names.append(name)
        elif language == "java" and "(" in stripped and not stripped.startswith("//"):
            # Heuristic: look for method-like patterns
            tokens = stripped.split("(")[0].split()
            if len(tokens) >= 2 and tokens[-1].isidentifier():
                names.append(tokens[-1])
    return names[:50]  # ponytail: cap to avoid noise on large files


def _extract_imports(content: str, language: str) -> list[str]:
    """Simple import extraction."""
    imports: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if language == "python" and (stripped.startswith("import ") or stripped.startswith("from ")):
            imports.append(stripped)
        elif language in ("javascript", "typescript") and ("require(" in stripped or "import " in stripped):
            imports.append(stripped)
        elif language == "go" and stripped.startswith('"') and stripped.endswith('"'):
            imports.append(stripped.strip('"'))
        elif language == "java" and stripped.startswith("import "):
            imports.append(stripped)
    return imports[:30]
