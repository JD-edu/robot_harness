"""Stage 6 실행 파일: package 실행과 파일 직접 실행을 모두 지원한다."""

import argparse
import sys
import time
from pathlib import Path

# 파일 경로로 실행할 때도 형제 package인 stage5와 stage6를 찾게 한다.
if __package__ in (None, ""):
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from stage5_mujoco_ik.environment import JDCobot200Environment
from stage5_mujoco_ik.viewer import GLFWRenderer
from stage6_contact_grasp.task import PickRedBlockTask


def main():
    parser = argparse.ArgumentParser(description="Stage 6 red block IK grasp")
    parser.add_argument("--viewer", action="store_true")
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()
    env = JDCobot200Environment()
    if not args.viewer:
        result = PickRedBlockTask(env).run()
    else:
        with GLFWRenderer(env) as viewer:
            result = PickRedBlockTask(env, step_callback=viewer.render).run()
            started = time.monotonic()
            while viewer.is_running() and time.monotonic() - started < args.duration:
                viewer.render()
                time.sleep(0.01)
    print("STAGE 6 RED BLOCK:", result)


if __name__ == "__main__":
    main()
