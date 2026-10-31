"""Smoke tests for the SKT latent-recursion method port."""

from __future__ import annotations

import pytest

import impro.mas
from impro.mas import cli as mas_cli
from impro.mas.inference.load_from_repo import STYLE_SPECS
from impro.mas.inference.prompts import get_system_prompt
from impro.mas.train.mas_prompt import get_system_prompt as get_train_system_prompt


def test_mas_package_exposes_a_version() -> None:
    assert impro.mas.__version__ == "0.1.0"


def test_all_released_collaboration_styles_are_present() -> None:
    assert set(STYLE_SPECS) == {
        "sequential_light",
        "sequential_scaled",
        "mixture",
        "distillation",
        "deliberation",
    }


def test_prompt_helpers_share_the_default_system_prompt() -> None:
    assert get_system_prompt() == "You are a helpful assistant."
    assert get_train_system_prompt() == "You are a helpful assistant."


def test_cli_help_is_available_without_the_gpu_stack(capsys: pytest.CaptureFixture[str]) -> None:
    assert mas_cli.main(["--help"]) == 0
    assert "SKT latent-space recursion" in capsys.readouterr().out


def test_inference_pipeline_imports_when_optional_stack_is_installed() -> None:
    pytest.importorskip("transformers")
    pytest.importorskip("datasets")
    pytest.importorskip("huggingface_hub")

    from impro.mas.inference import run, system_loader

    assert callable(run.main)
    assert callable(system_loader.load_mas_system)
