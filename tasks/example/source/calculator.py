"""A two-function calculator, one of which is wrong."""

from __future__ import annotations


def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left - right


def multiply(left: int, right: int) -> int:
    """Return the product of two integers."""
    return left * right
