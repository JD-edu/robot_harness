from common.skill_api import RobotSkill, SkillResult, SkillStatus


def fail(msg: str) -> SkillResult:
    return SkillResult(SkillStatus.FAILURE, msg)


class PickSkill(RobotSkill):
    name = "pick"
    description = "Pick an object with the specified arm."
    parameters = {"arm": "left|right", "object": "object name"}

    def validate_args(self, args):
        super().validate_args(args)
        if args["arm"] not in {"left", "right"}:
            raise ValueError("arm must be left or right")
        if not isinstance(args["object"], str) or not args["object"]:
            raise ValueError("object must be a non-empty string")

    def execute(self, ctx, **kwargs):
        arm, name = kwargs.get("arm"), kwargs.get("object")
        if ctx.robot.held(arm) is not None:
            return fail(f"{arm} hand is not empty")
        obj = ctx.world.get(name)
        if obj.held_by is not None:
            return fail(f"{name} is already held")
        obj.held_by = arm
        obj.location = "held"
        ctx.robot.set_held(arm, name)
        return SkillResult(SkillStatus.SUCCESS, f"{arm} picked {name}")


class PlaceSkill(RobotSkill):
    name = "place"
    description = "Place the currently held object at a named location."
    parameters = {"arm": "left|right", "location": "location name"}

    def validate_args(self, args):
        super().validate_args(args)
        if args["arm"] not in {"left", "right"}:
            raise ValueError("arm must be left or right")
        if not isinstance(args["location"], str) or not args["location"]:
            raise ValueError("location must be a non-empty string")

    def execute(self, ctx, **kwargs):
        arm, location = kwargs.get("arm"), kwargs.get("location")
        name = ctx.robot.held(arm)
        if name is None:
            return fail(f"{arm} hand is empty")
        obj = ctx.world.get(name)
        obj.held_by = None
        obj.location = location
        ctx.robot.set_held(arm, None)
        return SkillResult(SkillStatus.SUCCESS, f"placed {name} at {location}")


class OpenCapSkill(RobotSkill):
    name = "open_cap"
    description = "Open the cap of a PET bottle. One arm must stabilize the PET and the other arm must be free."
    parameters = {"holder_arm": "left|right", "worker_arm": "left|right", "object": "PET bottle name"}

    def validate_args(self, args):
        super().validate_args(args)
        if args["holder_arm"] not in {"left", "right"} or args["worker_arm"] not in {"left", "right"}:
            raise ValueError("arms must be left or right")
        if not isinstance(args["object"], str) or not args["object"]:
            raise ValueError("object must be a non-empty string")

    def execute(self, ctx, **kwargs):
        holder, worker, name = kwargs.get("holder_arm"), kwargs.get("worker_arm"), kwargs.get("object")
        if holder == worker:
            return fail("holder_arm and worker_arm must differ")
        obj = ctx.world.get(name)
        if obj.kind != "pet_bottle":
            return fail(f"{name} is not a PET bottle")
        if ctx.robot.held(holder) != name:
            return fail(f"{holder} arm is not holding {name}")
        if ctx.robot.held(worker) is not None:
            return fail(f"{worker} hand must be free")
        obj.cap_open = True
        return SkillResult(SkillStatus.SUCCESS, f"opened cap of {name}")
