"""JDCobot200의 실제 MuJoCo 모델을 사용하는 IK 제어기."""

from __future__ import annotations

from typing import Iterable

import numpy as np

if __package__:
    from .jdcobot200_mink_solver import JDCobot200MinkSolver
else:
    from jdcobot200_mink_solver import JDCobot200MinkSolver


class IKSolver:
    """Mink differential IK를 MuJoCo position actuator에 연결한다."""

    def __init__(self, env, max_iterations=400, tolerance=0.005, ik_substeps=4, simulation_steps=2):
        self.env = env
        self.max_iterations = int(max_iterations)
        self.tolerance = float(tolerance)
        self.ik_substeps = int(ik_substeps)
        self.simulation_steps = int(simulation_steps)
        if self.max_iterations < 1 or self.tolerance <= 0:
            raise ValueError("max_iterations와 tolerance는 양수여야 합니다.")
        self.backend = JDCobot200MinkSolver(env.model, end_effector_site=env.END_EFFECTOR_SITE)

    @staticmethod
    def _target(target: Iterable[float]) -> np.ndarray:
        value = np.asarray(target, dtype=float)
        if value.shape != (3,) or not np.all(np.isfinite(value)):
            raise ValueError("target은 유한한 xyz 값 3개여야 합니다.")
        return value

    def solve(self, target: Iterable[float]) -> dict[str, object]:
        """현재 자세에서 목표점의 관절 해를 계산하되 simulation은 변경하지 않는다."""
        target_value = self._target(target)
        self.backend.reset(self.env.data.qpos.copy())
        self.backend.set_target_position(target_value)
        result = self.backend.solve_step(
            self.env.data.qpos.copy(),
            # Offline solve에는 충분한 가상 시간을 주어 velocity limit가
            # 관절 해 탐색 범위를 불필요하게 제한하지 않게 한다.
            dt=2.0,
            iterations=max(self.ik_substeps * 50, 200),
        )
        ok = result.solution_found and result.position_error <= self.tolerance
        return self._result(ok, result, iterations=1)

    def move_to(self, target: Iterable[float], step_callback=None) -> dict[str, object]:
        """폐루프 IK와 MuJoCo dynamics를 반복해 end-effector를 이동한다."""
        target_value = self._target(target)
        self.backend.reset(self.env.data.qpos.copy())
        self.backend.set_target_position(target_value)
        last = None
        iteration = 0
        for iteration in range(1, self.max_iterations + 1):
            last = self.backend.solve_step(
                self.env.data.qpos.copy(),
                dt=self.env.timestep * self.simulation_steps,
                iterations=self.ik_substeps,
            )
            self.env.command_arm(last.arm_qpos)
            self.env.step(self.simulation_steps)
            if step_callback is not None:
                step_callback()
            error = float(np.linalg.norm(target_value - self.env.gripper_position()))
            if error <= self.tolerance:
                return self._simulation_result(True, target_value, error, iteration, last.solution_found)
            if not last.solution_found:
                break
        error = float(np.linalg.norm(target_value - self.env.gripper_position()))
        return self._simulation_result(False, target_value, error, iteration, bool(last and last.solution_found))

    def _result(self, ok, result, iterations):
        return {
            "ok": bool(ok),
            "code": "IK_SUCCESS" if ok else "IK_UNREACHABLE",
            "joints": result.arm_qpos.copy(),
            "error": float(result.position_error),
            "position": result.current_position.copy(),
            "target": result.target_position.copy(),
            "iterations": int(iterations),
        }

    def _simulation_result(self, ok, target, error, iterations, solution_found):
        return {
            "ok": bool(ok),
            "code": "IK_SUCCESS" if ok else "IK_UNREACHABLE",
            "joints": self.env.arm_positions(),
            "error": float(error),
            "position": self.env.gripper_position(),
            "target": target.copy(),
            "iterations": int(iterations),
            "solution_found": bool(solution_found),
        }
