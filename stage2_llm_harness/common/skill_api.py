"""Stage 2의 Robot Skill이 함께 사용하는 간단한 클래스들입니다."""


class SkillStatus:
    """Skill의 실행 상태입니다."""

    SUCCESS = "success"
    FAILURE = "failure"
    REJECTED = "rejected"


class SkillResult:
    """Skill을 실행한 결과를 담습니다."""

    def __init__(self, status, message="", data=None):
        self.status = status
        self.message = message

        if data is None:
            data = {}
        self.data = data

        self.ok = status == SkillStatus.SUCCESS


class SkillContext:
    """Skill이 사용할 로봇과 주변 환경을 담습니다."""

    def __init__(self, robot, world):
        self.robot = robot
        self.world = world


class RobotSkill:
    """모든 Robot Skill의 부모 클래스입니다."""

    name = ""
    description = ""
    parameters = {}

    def execute(self, context, **args):
        raise NotImplementedError("execute()를 구현해야 합니다")

    def schema(self):
        """Planner에게 보여 줄 Skill 설명을 만듭니다."""

        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
