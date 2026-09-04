try:
    from stage2_llm_harness.common.skill_api import RobotSkill, SkillResult, SkillStatus
except ModuleNotFoundError:
    from common.skill_api import RobotSkill, SkillResult, SkillStatus


def fail(message):
    return SkillResult(SkillStatus.FAILURE, message)


class PickSkill(RobotSkill):
    name = "pick"
    description = "Pick an object with the specified arm."
    parameters = {"arm": "left|right", "object": "object name"}

    def validate_args(self, args):
        super().validate_args(args)
        if args["arm"] not in ("left", "right"):
            raise ValueError("arm must be left or right")
        if not isinstance(args["object"], str) or not args["object"]:
            raise ValueError("object must be a non-empty string")

    def execute(self, ctx, **kwargs):
        arm = kwargs.get("arm")
        name = kwargs.get("object")
        if ctx.robot.held(arm) is not None:
            return fail("{} hand is not empty".format(arm))
        obj = ctx.world.get(name)
        if obj.held_by is not None:
            return fail("{} is already held".format(name))
        obj.held_by = arm
        obj.location = "held"
        ctx.robot.set_held(arm, name)
        return SkillResult(SkillStatus.SUCCESS, "{} picked {}".format(arm, name))


class PlaceSkill(RobotSkill):
    name = "place"
    description = "Place the currently held object at a named location."
    parameters = {"arm": "left|right", "location": "location name"}

    def validate_args(self, args):
        super().validate_args(args)
        if args["arm"] not in ("left", "right"):
            raise ValueError("arm must be left or right")
        if not isinstance(args["location"], str) or not args["location"]:
            raise ValueError("location must be a non-empty string")

    def execute(self, ctx, **kwargs):
        arm = kwargs.get("arm")
        location = kwargs.get("location")
        name = ctx.robot.held(arm)
        if name is None:
            return fail("{} hand is empty".format(arm))
        obj = ctx.world.get(name)
        obj.held_by = None
        obj.location = location
        ctx.robot.set_held(arm, None)
        return SkillResult(SkillStatus.SUCCESS, "placed {} at {}".format(name, location))


class OpenCapSkill(RobotSkill):
    name = "open_cap"
    description = "Open a PET cap while the other arm holds the bottle."
    parameters = {
        "holder_arm": "left|right",
        "worker_arm": "left|right",
        "object": "PET bottle name",
    }

    def validate_args(self, args):
        super().validate_args(args)
        if args["holder_arm"] not in ("left", "right"):
            raise ValueError("arms must be left or right")
        if args["worker_arm"] not in ("left", "right"):
            raise ValueError("arms must be left or right")
        if not isinstance(args["object"], str) or not args["object"]:
            raise ValueError("object must be a non-empty string")

    def execute(self, ctx, **kwargs):
        holder = kwargs.get("holder_arm")
        worker = kwargs.get("worker_arm")
        name = kwargs.get("object")
        if holder == worker:
            return fail("holder_arm and worker_arm must differ")
        obj = ctx.world.get(name)
        if obj.kind != "pet_bottle":
            return fail("{} is not a PET bottle".format(name))
        if ctx.robot.held(holder) != name:
            return fail("{} arm is not holding {}".format(holder, name))
        if ctx.robot.held(worker) is not None:
            return fail("{} hand must be free".format(worker))
        obj.cap_open = True
        return SkillResult(SkillStatus.SUCCESS, "opened cap of {}".format(name))
