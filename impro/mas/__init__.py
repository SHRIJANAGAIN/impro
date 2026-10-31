"""SKT: latent-space recursion for multi-agent systems.

The inner loop trains each agent's role-specific inner latent adapter. The
outer loop connects the agents and trains the outer latent adapters through
the recursive rounds. Inference supports sequential, mixture, distillation and
deliberation collaboration styles.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
