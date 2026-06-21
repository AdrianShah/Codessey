"""A clean, well-written utility — should produce minimal findings."""

from typing import TypeVar, Iterable

T = TypeVar("T")


def chunk_list(items: list[T], size: int) -> list[list[T]]:
    """Split a list into chunks of the given size."""
    if size <= 0:
        raise ValueError("Chunk size must be positive")
    return [items[i:i + size] for i in range(0, len(items), size)]


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide two numbers, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def flatten(nested: Iterable[Iterable[T]]) -> list[T]:
    """Flatten one level of nesting."""
    return [item for sublist in nested for item in sublist]
