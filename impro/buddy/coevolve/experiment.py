"""Public entrypoint for configured model and co-evolution experiments."""

import argparse
import json
import os
from pathlib import Path

from impro.buddy.configuration import load_config, settings


def main():
    parser = argparse.ArgumentParser(
        prog="impro-buddy-experiment",
        description="Run model, harness_evolve, or co-evolution from one TOML file."
    )
    parser.add_argument("config", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse configuration without preparing assets or starting services",
    )
    args = parser.parse_args()
    args.config = args.config.resolve()
    config = load_config(args.config)
    os.environ["IMPRO_BUDDY_CONFIG_TOML"] = args.config.read_bytes().decode("utf-8")
    model = dict(config["model"])
    model_mode = model.pop("mode", "train")
    if config["mode"] == "model":
        command = [model_mode]
        if config.get("data"):
            command.extend(["--dataset", config["data"]["dataset"]])
        for key, value in model.items():
            if isinstance(value, bool):
                if value:
                    command.append("--" + key.replace("_", "-"))
            else:
                command.extend(["--" + key.replace("_", "-"), str(value)])
        if args.dry_run:
            print(json.dumps({"model_arguments": command, "started": False}, indent=2))
            return
        from impro.buddy.cli import main as model_main

        if config.get("experiment"):
            model_main(command, planned_run_dir=(args.config.parent / config["experiment"]).resolve())
        else:
            model_main(command)
        return
    cfg = settings()
    cfg.update(config.get("data", {}))
    cfg.update(model)
    if args.dry_run:
        print(json.dumps({"config": config, "runtime_settings": cfg, "started": False}, indent=2))
        return
    from impro.buddy.coevolve.loop import run

    run(config, cfg)


if __name__ == "__main__":
    main()
