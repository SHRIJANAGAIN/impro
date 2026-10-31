"""impro-buddy double recursion: harness search plus optional model training.

The inner recursion fixes the task model and searches complete Python
``run(task, api)`` harness programs against a validation split. The outer
recursion freezes the selected harness and trains the task model with GRPO,
then returns the exported model to the next harness phase.

The package is imported from :mod:`impro` as ``impro.buddy`` and exposed on
the command line as ``impro buddy`` and ``impro-buddy``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
