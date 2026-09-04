"""Stage 7 CLI: 실제 Qwen 계획을 받아 MuJoCo에서 실행한다."""

import argparse
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from stage2_llm_harness.llm_client import LLMConnectionError
from stage5_mujoco_ik.environment import JDCobot200Environment
from stage5_mujoco_ik.viewer import GLFWRenderer
from stage7_llm_mujoco_harness.planner import QwenSkillPlanner
from stage7_llm_mujoco_harness.task import LLMMujocoTask


def parse_args():
    parser = argparse.ArgumentParser(description="Stage 7 Qwen + MuJoCo Harness")
    parser.add_argument("command", nargs="?", default="빨간 블록을 집어서 들어 올려 주세요")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="qwen3-8b")
    parser.add_argument("--provider", choices=("auto", "openai", "ollama"), default="auto")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--viewer", action="store_true")
    parser.add_argument("--duration", type=float, default=5.0)
    return parser.parse_args()


def main():
    args = parse_args()
    env = JDCobot200Environment()
    planner = QwenSkillPlanner(args.base_url, args.model, args.provider, args.timeout)
    try:
        if not args.viewer:
            result = LLMMujocoTask(env, planner).run(args.command)
        else:
            with GLFWRenderer(env, title="Stage 7 - Qwen MuJoCo Harness") as viewer:
                result = LLMMujocoTask(env, planner, step_callback=viewer.render).run(args.command)
                started = time.monotonic()
                while viewer.is_running() and time.monotonic() - started < args.duration:
                    viewer.render()
                    time.sleep(0.01)
    except LLMConnectionError as error:
        result = {"ok": False, "code": "LLM_CONNECTION_ERROR", "message": str(error)}

    print("QWEN RAW RESPONSE:", planner.last_raw_response)
    print("STAGE 7 LLM MUJOCO:", result)
    return result


if __name__ == "__main__":
    outcome = main()
    raise SystemExit(0 if outcome["ok"] else 1)
