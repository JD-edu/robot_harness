class SkillStatus:
    SUCCESS = "success"
    FAILURE = "failure"
    REJECTED = "rejected"


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
