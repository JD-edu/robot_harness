"""복구 sequence를 하드코딩하지 않는 try-fail-replan-retry loop."""

import numpy as np

from stage6_contact_grasp.harness import Harness, SkillRegistry
from stage6_contact_grasp.skills import (
    GraspSkill,
    LiftSkill,
    MoveToObjectSkill,
    MoveToSkill,
)


class FailOnceSkill:
    """실제 복구 경로를 재현하기 위한 선택적 1회 실패 주입기."""

    def __init__(self, skill):
        self.skill = skill
        self.name = skill.name
        self.failed = False

    def schema(self):
        return self.skill.schema()

    def validate_args(self, args):
        return self.skill.validate_args(args)

    def execute(self, args):
        if not self.failed:
            self.failed = True
            return {
                "ok": False,
                "code": "GRASP_NO_CONTACT",
                "message": "Stage 8 demo: first contact reading was intentionally dropped",
            }
        return self.skill.execute(args)


class RetryHarnessTask:
    """실패 정보로 LLM을 다시 호출하되 실행과 retry 한도는 Harness가 통제한다."""

    def __init__(self, env, planner, max_retries=2, inject_first_failure=False,
                 step_callback=None):
        self.env = env
        self.planner = planner
        self.initial_block_z = float(env.body_position("red_block")[2])
        self.max_retries = int(max_retries)
        if not 0 <= self.max_retries <= 3:
            raise ValueError("max_retries must be between 0 and 3")

        move_to = MoveToSkill(env, step_callback=step_callback)
        self.grasp = GraspSkill(env)
        exposed_grasp = FailOnceSkill(self.grasp) if inject_first_failure else self.grasp
        skills = [
            MoveToObjectSkill(env, move_to),
            exposed_grasp,
            LiftSkill(env, move_to, self.grasp),
        ]
        self.harness = Harness(SkillRegistry(skills), max_steps=3)

    def state(self):
        observation = self.env.observation()
        observation["world"] = {
            "red_block": {
                "type": "block",
                "position": self.env.body_position("red_block").tolist(),
            }
        }
        observation["held_object"] = self.grasp.held_object
        return observation

    @staticmethod
    def _feedback(attempt, plan, failure, events):
        return {
            "attempt": attempt,
            "failure": {
                "code": failure.get("code", "UNKNOWN_FAILURE"),
                "message": failure.get("message", ""),
            },
            "previous_plan": plan,
            "completed_skills": [
                event["skill"] for event in events if event["result"].get("ok")
            ],
            "instruction": (
                "Use the latest state and failure to create a corrected plan. "
                "Do not repeat an action that is already complete unless required."
            ),
        }

    def run(self, command):
        attempts = []
        feedback = None
        for attempt in range(1, self.max_retries + 2):
            state_before = self.state()
            plan = self.planner.plan(
                command,
                self.harness.registry.schemas(),
                state_before,
                feedback=feedback,
            )
            try:
                execution = self.harness.run(plan)
            except (TypeError, ValueError) as error:
                failure = {"ok": False, "code": "PLAN_REJECTED", "message": str(error)}
                execution = {"ok": False, "failure": failure, "events": []}

            record = {
                "attempt": attempt,
                "plan": plan,
                "execution": execution,
                "state_before": state_before,
                "state_after": self.state(),
            }
            attempts.append(record)

            block_position = self.env.body_position("red_block")
            tcp_position = self.env.gripper_position()
            block_lifted = block_position[2] >= self.initial_block_z + 0.02
            block_near_tcp = float(np.linalg.norm(block_position - tcp_position)) <= 0.05
            goal_reached = (
                self.grasp.held_object == "red_block"
                and block_lifted
                and block_near_tcp
            )
            record["goal_check"] = {
                "held": self.grasp.held_object == "red_block",
                "lifted": bool(block_lifted),
                "near_tcp": bool(block_near_tcp),
                "block_tcp_distance": float(np.linalg.norm(block_position - tcp_position)),
                "block_lift": float(block_position[2] - self.initial_block_z),
            }

            if execution["ok"] and goal_reached:
                return {"ok": True, "code": "TASK_SUCCESS", "attempts": attempts,
                        "retries_used": attempt - 1}

            if execution["ok"]:
                failure = {
                    "ok": False,
                    "code": "GOAL_NOT_REACHED",
                    "message": "red_block is not lifted near the TCP",
                }
            else:
                failure = execution["failure"]
            feedback = self._feedback(attempt, plan, failure, execution["events"])

        return {"ok": False, "code": "RETRY_EXHAUSTED", "failure": feedback,
                "attempts": attempts, "retries_used": self.max_retries}
