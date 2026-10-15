"""가상 로봇이 실행할 수 있는 세 가지 Skill입니다."""

try:
    from stage1_symbolic_robot.common.skill_api import (
        RobotSkill,
        SkillResult,
        SkillStatus,
    )
except ModuleNotFoundError:
    from common.skill_api import RobotSkill, SkillResult, SkillStatus


def failure(message):
    """실패 결과를 만드는 작은 도우미 함수입니다."""

    return SkillResult(SkillStatus.FAILURE, message)


class PickSkill(RobotSkill):
    """물체를 한쪽 손으로 집습니다."""

    name = "pick"
    description = "Pick an object with one arm."
    parameters = {
        "arm": "left 또는 right",
        "object": "물체 이름",
    }

    def execute(self, context, **args):
        arm = args["arm"]
        object_name = args["object"]

        # 물체를 집으려면 그 손이 비어 있어야 합니다.
        if context.robot.held(arm) is not None:
            return failure(arm + " hand is not empty")

        obj = context.world.get(object_name)

        # 다른 손이 이미 들고 있는 물체는 다시 집을 수 없습니다.
        if obj.held_by is not None:
            return failure(object_name + " is already held")

        context.robot.set_held(arm, object_name)
        obj.held_by = arm
        obj.location = "held"

        return SkillResult(
            SkillStatus.SUCCESS,
            arm + " picked " + object_name,
        )


class PlaceSkill(RobotSkill):
    """손에 든 물체를 지정한 장소에 내려놓습니다."""

    name = "place"
    description = "Place the held object at a location."
    parameters = {
        "arm": "left 또는 right",
        "location": "내려놓을 장소",
    }

    def execute(self, context, **args):
        arm = args["arm"]
        location = args["location"]
        object_name = context.robot.held(arm)

        # 내려놓으려면 먼저 그 손에 물체가 있어야 합니다.
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
    """한 손으로 페트병을 잡고 다른 손으로 뚜껑을 엽니다."""

    name = "open_cap"
    description = "Open a PET bottle cap with two arms."
    parameters = {
        "holder_arm": "병을 잡는 팔",
        "worker_arm": "뚜껑을 여는 팔",
        "object": "페트병 이름",
    }

    def execute(self, context, **args):
        holder_arm = args["holder_arm"]
        worker_arm = args["worker_arm"]
        object_name = args["object"]

        if holder_arm == worker_arm:
            return failure("two different arms are required")

        obj = context.world.get(object_name)

        if obj.kind != "pet_bottle":
            return failure(object_name + " is not a PET bottle")

        # 한 손은 페트병을 잡고 있어야 합니다.
        if context.robot.held(holder_arm) != object_name:
            return failure(holder_arm + " arm is not holding " + object_name)

        # 다른 손은 뚜껑을 열기 위해 비어 있어야 합니다.
        if context.robot.held(worker_arm) is not None:
            return failure(worker_arm + " hand must be free")

        obj.cap_open = True

        return SkillResult(
            SkillStatus.SUCCESS,
            "opened cap of " + object_name,
        )
