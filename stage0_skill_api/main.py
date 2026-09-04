# 두 가지 실행 방법을 모두 지원한다.
# 1) 프로젝트 루트: python3 -m stage0_skill_api.main
# 2) 이 폴더 안:    python3 main.py
try:
    from stage0_skill_api.common.skill_api import RobotSkill, SkillContext, SkillResult
except ModuleNotFoundError:
    from common.skill_api import RobotSkill, SkillContext, SkillResult


class SaySkill(RobotSkill):
    name = "say"
    description = "Print a short message. Used only to test the Skill API."
    parameters = {"text": "string"}

    def execute(self, ctx: SkillContext, **kwargs):
        text = str(kwargs.get("text", ""))
        print(f"ROBOT: {text}")
        return SkillResult(True, "message printed", {"text": text})


def main():
    skill = SaySkill()
    print("Skill schema:", skill.schema())
    result = skill.execute(SkillContext(robot=None, world=None), text="Skill API ready")
    print("Result:", result)


if __name__ == "__main__":
    main()
