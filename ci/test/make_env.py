"""Generate a JSON file representing the Environmental Parameters for a lambda from stage_parameters"""
import argparse
import json


def make_env(module: str, stage: str) -> bool:
    """Generate a JSON file representing the Environmental Parameters for a lambda from stage_parameters"""
    with open(file="stage_parameters.json", mode="r", encoding="utf=8") as read_file:
        parameters = json.load(fp=read_file)
    environment_vars = {module: parameters[module][stage]}
    with open(f"ci/test/envs/{module}-{stage}.json", "w", encoding="utf-8") as write_file:
        json.dump(environment_vars, write_file, indent=2, default=str)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("module", help="function to build env vars for")
    parser.add_argument("stage", help="stage, dev or prod")
    args = parser.parse_args()
    make_env(module=args.module, stage=args.stage)
