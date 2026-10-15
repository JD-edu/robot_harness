"""Stage 1의 Skill에 입력 검사 기능을 추가한 코드입니다."""

try:
    from stage2_llm_harness.common.skill_api import (
        RobotSkill,
        SkillResult,
        SkillStatus,
    )
except ModuleNotFoundError:
    from common.skill_api import RobotSkill, SkillResult, SkillStatus


def failure(message):
    return SkillResult(SkillStatus.FAILURE, message)


class PickSkill(RobotSkill):
    name = "pick"
    description = "Pick an object with one arm."
    parameters = {
        "arm": "left 또는 right",
        "object": "물체 이름",
    }

    def validate_args(self, args):
        """LLM이 pick에 필요한 인자를 정확히 만들었는지 검사합니다."""

        if not isinstance(args, dict):
            raise ValueError("pick의 args는 딕셔너리여야 합니다")
        if "arm" not in args or "object" not in args:
            raise ValueError("pick에는 arm과 object가 필요합니다")
        if len(args) != 2:
            raise ValueError("pick에는 arm과 object만 사용할 수 있습니다")
        if args["arm"] != "left" and args["arm"] != "right":
            raise ValueError("arm은 left 또는 right여야 합니다")
        if not isinstance(args["object"], str) or args["object"] == "":
            raise ValueError("object는 비어 있지 않은 문자열이어야 합니다")

    def execute(self, context, **args):
        arm = args["arm"]
        object_name = args["object"]

        if context.robot.held(arm) is not None:
            return failure(arm + " hand is not empty")

        obj = context.world.get(object_name)

        if obj.held_by is not None:
            return failure(object_name + " is already held")

        context.robot.set_held(arm, object_name)
        obj.held_by = arm
        obj.location = "held"

        return SkillResult(SkillStatus.SUCCESS, arm + " picked " + object_name)


class PlaceSkill(RobotSkill):
    name = "place"
    description = "Place the held object at a location."
    parameters = {
        "arm": "left 또는 right",
        "location": "내려놓을 장소",
    }

    def validate_args(self, args):
        if not isinstance(args, dict):
            raise ValueError("place의 args는 딕셔너리여야 합니다")
        if "arm" not in args or "location" not in args:
            raise ValueError("place에는 arm과 location이 필요합니다")
        if len(args) != 2:
            raise ValueError("place에는 arm과 location만 사용할 수 있습니다")
        if args["arm"] != "left" and args["arm"] != "right":
            raise ValueError("arm은 left 또는 right여야 합니다")
        if not isinstance(args["location"], str) or args["location"] == "":
            raise ValueError("location은 비어 있지 않은 문자열이어야 합니다")

    def execute(self, context, **args):
        arm = args["arm"]
        location = args["location"]
        object_name = context.robot.held(arm)

        if object_name is None:
            return failure(arm + " hand is empty")

        obj = context.world.get(object_name)
        context.robot.set_held(arm, None)
        obj.held_by = None
        obj.location = location

        return SkillResult(
            SkillStatus.SUCCESS,
            "placed " + object_name + " at " + location,
        )


class OpenCapSkill(RobotSkill):
    name = "open_cap"
    description = "Open a PET bottle cap with two arms."
    parameters = {
        "holder_arm": "병을 잡는 팔",
        "worker_arm": "뚜껑을 여는 팔",
        "object": "페트병 이름",
    }

    def validate_args(self, args):
        if not isinstance(args, dict):
            raise ValueError("open_cap의 args는 딕셔너리여야 합니다")

        if "holder_arm" not in args:
            raise ValueError("open_cap에는 holder_arm이 필요합니다")
        if "worker_arm" not in args:
            raise ValueError("open_cap에는 worker_arm이 필요합니다")
        if "object" not in args:
            raise ValueError("open_cap에는 object가 필요합니다")
        if len(args) != 3:
            raise ValueError("open_cap에는 holder_arm, worker_arm, object만 사용합니다")

        arms = ("left", "right")
        if args["holder_arm"] not in arms or args["worker_arm"] not in arms:
            raise ValueError("팔은 left 또는 right여야 합니다")
        if not isinstance(args["object"], str) or args["object"] == "":
            raise ValueError("object는 비어 있지 않은 문자열이어야 합니다")

    def execute(self, context, **args):
        holder_arm = args["holder_arm"]
        worker_arm = args["worker_arm"]
        object_name = args["object"]

        if holder_arm == worker_arm:
            return failure("two different arms are required")

        obj = context.world.get(object_name)

        if obj.kind != "pet_bottle":
            return failure(object_name + " is not a PET bottle")
        if context.robot.held(holder_arm) != object_name:
            return failure(holder_arm + " arm is not holding " + object_name)
        if context.robot.held(worker_arm) is not None:
            return failure(worker_arm + " hand must be free")

        obj.cap_open = True
        return SkillResult(SkillStatus.SUCCESS, "opened cap of " + object_name)
