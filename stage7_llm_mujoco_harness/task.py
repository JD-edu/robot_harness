"""Qwen 계획을 Stage 6 Harness로 검증하고 MuJoCo에서 실행한다."""

import numpy as np

from stage6_contact_grasp.harness import Harness, SkillRegistry
from stage6_contact_grasp.skills import (
    GraspSkill,
    LiftSkill,
    MoveToObjectSkill,
    MoveToSkill,
)


class LLMMujocoTask:
    def __init__(self, env, planner, step_callback=None):
        self.env = env
        self.planner = planner
        self.initial_block_z = float(env.body_position("red_block")[2])
        move_to = MoveToSkill(env, step_callback=step_callback)
        self.grasp = GraspSkill(env)
        skills = [
            MoveToObjectSkill(env, move_to),
            self.grasp,
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

    def run(self, command):
        before = self.state()
        plan = self.planner.plan(command, self.harness.registry.schemas(), before)
        try:
            execution = self.harness.run(plan)
        except (TypeError, ValueError) as error:
            return {
                "ok": False,
                "code": "PLAN_REJECTED",
                "message": str(error),
                "plan": plan,
                "state_before": before,
            }

        if not execution["ok"]:
            return {
                "ok": False,
                "code": "SKILL_FAILED",
                "plan": plan,
                "execution": execution,
                "state_before": before,
                "state_after": self.state(),
            }
        block = self.env.body_position("red_block")
        distance = float(np.linalg.norm(block - self.env.gripper_position()))
        goal_reached = (
            self.grasp.held_object == "red_block"
            and block[2] >= self.initial_block_z + 0.02
            and distance <= 0.05
        )
        if not goal_reached:
            return {
                "ok": False,
                "code": "GOAL_NOT_REACHED",
                "message": "red_block was not lifted near the TCP",
                "plan": plan,
                "execution": execution,
                "state_before": before,
                "state_after": self.state(),
            }
        return {
            "ok": True,
            "code": "TASK_SUCCESS",
            "plan": plan,
            "execution": execution,
            "state_before": before,
            "state_after": self.state(),
        }
