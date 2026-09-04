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


class RobotSkill:
    name = ""
    description = ""
    parameters = {}

    def execute(self, ctx, **kwargs):
        raise NotImplementedError("execute()를 구현해야 합니다")

    def validate_args(self, args):
        expected = set(self.parameters.keys())
        actual = set(args.keys())
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                "invalid arguments (missing={}, extra={})".format(missing, extra)
            )

    def schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
