"""LLM 없이 고정 JSON 계획을 Harness로 실행하는 빨간 블록 pick task."""

from stage6_contact_grasp.harness import Harness, SkillRegistry
from stage6_contact_grasp.skills import (
    GraspSkill,
    LiftSkill,
    MoveToObjectSkill,
    MoveToSkill,
)


PICK_RED_BLOCK_PLAN = [
    {"skill": "move_to_object", "args": {"object": "red_block"}},
    {"skill": "grasp", "args": {"object": "red_block"}},
    {"skill": "lift", "args": {"dz": 0.05}},
]


class PickRedBlockTask:
    def __init__(self, env, step_callback=None):
        move_to = MoveToSkill(env, step_callback=step_callback)
        grasp = GraspSkill(env)
        exposed_skills = [
            MoveToObjectSkill(env, move_to),
            grasp,
            LiftSkill(env, move_to, grasp),
        ]
        self.harness = Harness(SkillRegistry(exposed_skills), max_steps=3)

    def run(self):
        result = self.harness.run(PICK_RED_BLOCK_PLAN)
        if result["ok"]:
            result["held_object"] = "red_block"
        return result
