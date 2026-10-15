import unittest

from stage2_llm_harness.common.skill_api import SkillContext
from stage2_llm_harness.harness import Harness, SkillRegistry, extract_json
from stage2_llm_harness.llm_client import MockPlanner
from stage2_llm_harness.main import build_world
from stage2_llm_harness.skills import OpenCapSkill, PickSkill, PlaceSkill


class Stage2LLMHarnessTests(unittest.TestCase):
    def build_harness(self):
        skills = [PickSkill(), PlaceSkill(), OpenCapSkill()]
        return Harness(SkillRegistry(skills))

    def test_mock_plan_is_checked_and_executed(self):
        robot, world = build_world()
        context = SkillContext(robot, world)
        harness = self.build_harness()
        planner = MockPlanner()

        plan = planner.plan("페트병 뚜껑을 열어", harness.registry.schemas())
        success = harness.run(context, plan)

        self.assertTrue(success)
        self.assertTrue(world.get("pet").cap_open)

    def test_unknown_skill_is_rejected(self):
        harness = self.build_harness()
        plan = [{"skill": "fly", "args": {}}]

        with self.assertRaisesRegex(ValueError, "알 수 없는 Skill"):
            harness.validate_plan(plan)

    def test_missing_skill_argument_is_rejected(self):
        harness = self.build_harness()
        plan = [{"skill": "pick", "args": {"arm": "left"}}]

        with self.assertRaisesRegex(ValueError, "arm과 object"):
            harness.validate_plan(plan)

    def test_json_text_is_changed_to_python_list(self):
        text = '```json\n[{"skill": "pick", "args": {}}]\n```'

        plan = extract_json(text)

        self.assertEqual(plan[0]["skill"], "pick")


if __name__ == "__main__":
    unittest.main()
