class SkillResult:
    def __init__(self, success, message="", data=None):
        self.success = success
        self.message = message
        self.data = data or {}

    def __repr__(self):
        return "SkillResult(success={!r}, message={!r}, data={!r})".format(
            self.success, self.message, self.data
        )


class SkillContext:
    def __init__(self, robot, world):
        self.robot = robot
        self.world = world


class RobotSkill:
    name = ""
    description = ""
    parameters = {}

    def execute(self, ctx, **kwargs):
        raise NotImplementedError("execute()를 구현해야 합니다")

    def schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
