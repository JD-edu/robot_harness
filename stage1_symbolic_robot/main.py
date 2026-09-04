from common.skill_api import SkillContext
from symbolic_robot import ObjectState, SymbolicRobot, SymbolicWorld
from skills import OpenCapSkill, PickSkill, PlaceSkill


def main():
    world = SymbolicWorld()
    world.add(ObjectState("pet", "pet_bottle", "table"))
    world.add(ObjectState("cup", "cup", "table"))
    robot = SymbolicRobot()
    ctx = SkillContext(robot=robot, world=world)

    sequence = [
        (PickSkill(), {"arm": "left", "object": "pet"}),
        (OpenCapSkill(), {"holder_arm": "left", "worker_arm": "right", "object": "pet"}),
        (PlaceSkill(), {"arm": "left", "location": "table"}),
    ]

    for skill, args in sequence:
        result = skill.execute(ctx, **args)
        print(f"{skill.name}: {result.status} - {result.message}")

    print("WORLD:", world.snapshot())
    print("ROBOT:", robot)


if __name__ == "__main__":
    main()
