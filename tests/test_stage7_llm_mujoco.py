import unittest

from stage5_mujoco_ik.environment import JDCobot200Environment
from stage7_llm_mujoco_harness.task import LLMMujocoTask


class FakePlanner:
    def __init__(self, plan):
        self.result = plan
        self.received = None

    def plan(self, command, skill_schemas, state):
        self.received = {"command": command, "skills": skill_schemas, "state": state}
        return self.result


class Stage7LLMMujocoTests(unittest.TestCase):
    def test_llm_plan_drives_real_mujoco_skills(self):
        plan = [
            {"skill": "move_to_object", "args": {"object": "red_block"}},
            {"skill": "grasp", "args": {"object": "red_block"}},
            {"skill": "lift", "args": {"dz": 0.05}},
        ]
        env = JDCobot200Environment()
        initial_z = env.body_position("red_block")[2]
        planner = FakePlanner(plan)

        result = LLMMujocoTask(env, planner).run("빨간 블록을 들어 올려")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["plan"], plan)
        self.assertIn("red_block", planner.received["state"]["world"])
        self.assertNotIn("move_to", [item["name"] for item in planner.received["skills"]])
        self.assertGreater(env.body_position("red_block")[2], initial_z + 0.02)

    def test_harness_rejects_llm_hallucinated_skill(self):
        planner = FakePlanner([{"skill": "set_motor", "args": {"joint": 1}}])
        result = LLMMujocoTask(JDCobot200Environment(), planner).run("모터를 움직여")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "PLAN_REJECTED")

    def test_valid_but_incomplete_plan_fails_goal_check(self):
        planner = FakePlanner([
            {"skill": "move_to_object", "args": {"object": "red_block"}},
        ])
        result = LLMMujocoTask(JDCobot200Environment(), planner).run("빨간 블록을 들어 올려")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "GOAL_NOT_REACHED")


if __name__ == "__main__":
    unittest.main()
