import unittest

from stage1_symbolic_robot.common.skill_api import SkillStatus
from stage1_symbolic_robot.main import build_context
from stage1_symbolic_robot.skills import OpenCapSkill, PickSkill, PlaceSkill


class Stage1SymbolicRobotTests(unittest.TestCase):
    def test_pick_open_and_place(self):
        context = build_context()

        pick_result = PickSkill().execute(
            context,
            arm="left",
            object="pet",
        )
        open_result = OpenCapSkill().execute(
            context,
            holder_arm="left",
            worker_arm="right",
            object="pet",
        )
        place_result = PlaceSkill().execute(
            context,
            arm="left",
            location="table",
        )

        self.assertEqual(pick_result.status, SkillStatus.SUCCESS)
        self.assertEqual(open_result.status, SkillStatus.SUCCESS)
        self.assertEqual(place_result.status, SkillStatus.SUCCESS)
        self.assertTrue(context.world.get("pet").cap_open)
        self.assertIsNone(context.robot.left_hand)

    def test_open_cap_fails_when_robot_is_not_holding_bottle(self):
        context = build_context()

        result = OpenCapSkill().execute(
            context,
            holder_arm="left",
            worker_arm="right",
            object="pet",
        )

        self.assertEqual(result.status, SkillStatus.FAILURE)
        self.assertFalse(context.world.get("pet").cap_open)


if __name__ == "__main__":
    unittest.main()
