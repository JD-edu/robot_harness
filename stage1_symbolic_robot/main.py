"""Stage 1의 Skill을 순서대로 실행하는 예제입니다."""

# 프로젝트 폴더에서 ``python -m stage1_symbolic_robot.main``으로 실행할 때
try:
    from stage1_symbolic_robot.common.skill_api import SkillContext
    from stage1_symbolic_robot.symbolic_robot import (
        ObjectState,
        SymbolicRobot,
        SymbolicWorld,
    )
    from stage1_symbolic_robot.skills import OpenCapSkill, PickSkill, PlaceSkill

# ``python stage1_symbolic_robot/main.py``처럼 파일을 직접 실행할 때
except ModuleNotFoundError:
    from common.skill_api import SkillContext
    from symbolic_robot import ObjectState, SymbolicRobot, SymbolicWorld
    from skills import OpenCapSkill, PickSkill, PlaceSkill


def build_context():
    """예제에서 사용할 로봇과 주변 환경을 만듭니다."""

    robot = SymbolicRobot()

    world = SymbolicWorld()
    world.add(ObjectState("pet", "pet_bottle", "table"))
    world.add(ObjectState("cup", "cup", "table"))

    return SkillContext(robot, world)


def main():
    context = build_context()

    # 아직 LLM은 사용하지 않습니다.
    # 실행할 Skill과 인자를 사람이 미리 정합니다.
    sequence = [
        (PickSkill(), {"arm": "left", "object": "pet"}),
        (
            OpenCapSkill(),
            {
                "holder_arm": "left",
                "worker_arm": "right",
                "object": "pet",
            },
        ),
        (PlaceSkill(), {"arm": "left", "location": "table"}),
    ]

    for skill, args in sequence:
        result = skill.execute(context, **args)
        print(skill.name + ": " + result.status + " - " + result.message)

        if result.ok is False:
            print("Skill이 실패했으므로 실행을 멈춥니다.")
            break

    print("WORLD:", context.world.snapshot())
    print("ROBOT:", context.robot.snapshot())


if __name__ == "__main__":
    main()
