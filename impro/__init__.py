# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""`impro`: SKT recursive harness improvement for any coding agent.

The complete SKT recursive-harness framework is present:

* ``impro.core`` -- the method (recursion, prompts, selection, library);
* ``impro.substrate`` -- OpenCode, Codex and the coding-agent surface;
* ``impro.benchmarks`` -- JobBench, WorkBuddy and LAB reproductions;
* ``impro.cli`` -- adaptation, judging, reporting and the coding workflow;
* ``impro.buddy`` -- impro-buddy double recursion: Python harness search
  plus optional SkyRL model training;
* ``impro.mas`` -- SKT latent-space recursion and the inner/outer multi-agent
  training loops;
* ``impro.demo``, ``impro.install`` and ``impro.preflight`` -- the bundled
  deterministic demo and benchmark setup/readiness checks.

A coding task is a directory with ``TASK.md`` and an optional ``source/``
tree. The agent is any command that reads a prompt on stdin and writes its
final reply to stdout.
"""

from __future__ import annotations

from . import buddy, mas

__version__ = "0.1.0"

__all__ = ["__version__", "buddy", "mas"]
