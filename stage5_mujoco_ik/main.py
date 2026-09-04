"""Stage 5: JDCobot200 MuJoCo + Mink IK 실행 예제."""

from __future__ import annotations

import argparse
import time

import numpy as np

if __package__:
    from stage5_mujoco_ik.environment import JDCobot200Environment
    from stage5_mujoco_ik.ik import IKSolver
    from stage5_mujoco_ik.viewer import GLFWRenderer
else:
    from environment import JDCobot200Environment
    from ik import IKSolver
    from viewer import GLFWRenderer


def main() -> None:
    parser = argparse.ArgumentParser(description="JDCobot200 MuJoCo IK demo")
    parser.add_argument("--target", nargs=3, type=float, metavar=("X", "Y", "Z"))
    parser.add_argument("--viewer", action="store_true", help="MuJoCo viewer 창에서 IK 동작 보기")
    parser.add_argument(
        "--duration", type=float, default=0.0,
        help="IK 완료 후 viewer 유지 시간(초), 0이면 창을 닫을 때까지 유지",
    )
    args = parser.parse_args()

    env = JDCobot200Environment()
    start = env.gripper_position()
    target = np.asarray(args.target, dtype=float) if args.target else start + [0.0, 0.01, 0.0]
    env.set_target_marker(target)
    solver = IKSolver(env)

    if args.viewer:
        result = run_viewer(env, solver, target, args.duration)
    else:
        result = solver.move_to(target)
    printable = {key: value.tolist() if isinstance(value, np.ndarray) else value for key, value in result.items()}
    print("STAGE 5 MUJOCO IK:", printable)


def run_viewer(env, solver, target, duration):
    """GLFW window를 연 상태에서 controller iteration을 렌더링한다."""
    with GLFWRenderer(env) as viewer:
        def render_step():
            viewer.render()
            time.sleep(max(env.timestep * solver.simulation_steps, 0.01))

        viewer.render()
        result = solver.move_to(target, step_callback=render_step)
        viewer.render()
        started = time.monotonic()
        while viewer.is_running() and (duration <= 0 or time.monotonic() - started < duration):
            viewer.render()
            time.sleep(0.01)
        return result


if __name__ == "__main__":
    main()
