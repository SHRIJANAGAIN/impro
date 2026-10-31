"""Evaluation-only using the same harness and generator as training."""

import asyncio
import os
import sys

import ray
from skyrl.train.config import SkyRLTrainConfig
from skyrl.train.entrypoints.main_generate import EvalOnlyEntrypoint
from skyrl.train.evaluate import evaluate_step_wise
from skyrl.train.utils.trainer_utils import build_dataloader
from skyrl.train.utils.utils import initialize_ray, validate_generator_cfg

from impro.buddy.artifacts import write_json
from impro.buddy.inference.lifecycle import InferenceLifecycle
from impro.buddy.training.generator import BuddyGenerator, load_settings
from impro.buddy.training.tracking import ExperimentTracking


class BuddyEval(ExperimentTracking, InferenceLifecycle, EvalOnlyEntrypoint):
    # Evaluation has no training-side weight sync to restore discarded weights.
    evaluation_only = True

    async def run(self, client):
        try:
            await client.wake_up()
            generator = self.get_generator(self.cfg, self.tokenizer, client)
            metrics = await evaluate_step_wise(
                eval_dataloader=build_dataloader(self.cfg, self.eval_dataset, is_train=False),
                generator=generator, cfg=self.cfg, global_step=None, tokenizer=self.tokenizer,
            )
            metrics.update(generator.evaluation_metrics())
            self.get_tracker().log(metrics, step=0, commit=True)
            return metrics
        finally:
            await client.aclose()

    def get_generator(self, cfg, tokenizer, inference_engine_client):
        return BuddyGenerator(
            cfg.generator,
            inference_engine_client,
            tokenizer,
            load_settings(os.environ["SKYRL_IMPRO_BUDDY_SETTINGS"]),
        )


@ray.remote(num_cpus=1)
def evaluate(cfg):
    exp = BuddyEval(cfg)
    client = exp.get_inference_client()
    return asyncio.run(exp.run(client))


def main():
    cfg = SkyRLTrainConfig.from_cli_overrides(sys.argv[1:])
    validate_generator_cfg(cfg)
    initialize_ray(cfg)
    try:
        metrics = ray.get(evaluate.remote(cfg))
        from pathlib import Path

        settings = load_settings(os.environ["SKYRL_IMPRO_BUDDY_SETTINGS"])
        write_json(Path(settings["run_dir"]) / "evaluation.json", metrics)
    finally:
        ray.shutdown()
