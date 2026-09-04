import unittest

from stage5_mujoco_ik.environment import JDCobot200Environment
from stage8_retry_harness.recovery import RetryHarnessTask


class ScriptedPlanner:
    def __init__(self, plans):
        self.plans = plans
        self.calls = []

    def plan(self, command, schemas, state, feedback=None):
        self.calls.append({"state": state, "feedback": feedback})
        return self.plans[min(len(self.calls) - 1, len(self.plans) - 1)]


FULL_PLAN = [
    {"skill": "move_to_object", "args": {"object": "red_block"}},
    {"skill": "grasp", "args": {"object": "red_block"}},
    {"skill": "lift", "args": {"dz": 0.05}},
]


class Stage8RetryHarnessTests(unittest.TestCase):
    def test_failure_is_sent_to_llm_and_new_plan_succeeds(self):
        recovery_plan = [
            {"skill": "grasp", "args": {"object": "red_block"}},
            {"skill": "lift", "args": {"dz": 0.05}},
        ]
        planner = ScriptedPlanner([FULL_PLAN, recovery_plan])
        result = RetryHarnessTask(
            JDCobot200Environment(), planner, max_retries=2,
            inject_first_failure=True,
        ).run("빨간 블록을 들고 실패하면 다시 계획해")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["retries_used"], 1)
        self.assertEqual(len(planner.calls), 2)
        self.assertEqual(
            planner.calls[1]["feedback"]["failure"]["code"],
            "GRASP_NO_CONTACT",
        )
        self.assertEqual(planner.calls[1]["feedback"]["completed_skills"],
                         ["move_to_object"])
        final_check = result["attempts"][-1]["goal_check"]
        self.assertTrue(final_check["lifted"])
        self.assertTrue(final_check["near_tcp"])
        self.assertLess(final_check["block_tcp_distance"], 0.05)

    def test_retry_budget_is_enforced_by_harness(self):
        bad = [{"skill": "invented_skill", "args": {}}]
        planner = ScriptedPlanner([bad])
        result = RetryHarnessTask(
            JDCobot200Environment(), planner, max_retries=1,
        ).run("실패하면 계속 시도해")

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "RETRY_EXHAUSTED")
        self.assertEqual(len(planner.calls), 2)

    def test_retry_limit_cannot_be_unbounded(self):
        with self.assertRaises(ValueError):
            RetryHarnessTask(JDCobot200Environment(), ScriptedPlanner([FULL_PLAN]),
                             max_retries=100)


if __name__ == "__main__":
    unittest.main()
