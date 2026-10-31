"""The check the task asks to be green."""

from __future__ import annotations

from calculator import add, multiply

assert add(2, 3) == 5
assert add(-2, -3) == -5
assert add(0, 7) == 7
assert multiply(3, 4) == 12
print("ok")
