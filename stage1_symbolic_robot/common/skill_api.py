class SkillStatus:
    SUCCESS = "success"
    FAILURE = "failure"


class SkillResult:
    def __init__(self, status, message="", data=None):
        self.status = status
        self.message = message
        self.data = data or {}
        self.ok = status == SkillStatus.SUCCESS


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
