import argparse

# 프로젝트 루트에서 모듈로 실행하는 방법과
# Stage 2 폴더에서 main.py를 직접 실행하는 방법을 모두 지원한다.
try:
    from stage2_llm_harness.common.skill_api import SkillContext
    from stage2_llm_harness.symbolic_robot import ObjectState, SymbolicRobot, SymbolicWorld
    from stage2_llm_harness.skills import OpenCapSkill, PickSkill, PlaceSkill
    from stage2_llm_harness.harness import Harness, SkillRegistry, extract_json
    from stage2_llm_harness.llm_client import LocalLLMPlanner, MockPlanner
except ModuleNotFoundError:
    from common.skill_api import SkillContext
    from symbolic_robot import ObjectState, SymbolicRobot, SymbolicWorld
    from skills import OpenCapSkill, PickSkill, PlaceSkill
    from harness import Harness, SkillRegistry, extract_json
    from llm_client import LocalLLMPlanner, MockPlanner


def build_world():
    world = SymbolicWorld()
    world.add(ObjectState("pet", "pet_bottle", "table"))
    world.add(ObjectState("cup", "cup", "table"))
    return SymbolicRobot(), world


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", nargs="?", default="PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어")
    p.add_argument("--llm", action="store_true", help="use local OpenAI-compatible server")
    p.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    p.add_argument("--model", default="qwen3-8b")
    p.add_argument("--provider", choices=("auto", "ollama", "openai"), default="openai")
    p.add_argument("--timeout", type=float, default=120)
    args = p.parse_args()

    robot, world = build_world()
    ctx = SkillContext(robot=robot, world=world)
    registry = SkillRegistry([PickSkill(), PlaceSkill(), OpenCapSkill()])
    harness = Harness(registry)

    planner = LocalLLMPlanner(args.base_url, args.model, args.provider, args.timeout) if args.llm else MockPlanner()
    state = {
        "robot": {"left_hand": robot.left_hand, "right_hand": robot.right_hand},
        "world": world.snapshot(),
    }
    print(f"command: {args.command}")
    raw = planner.plan(args.command, registry.schemas(), state=state)
    print(f"raw: {raw}")
    plan = extract_json(raw) if isinstance(raw, str) else raw

    print("PLAN:", plan)
    ok = harness.run(ctx, plan)
    print("SUCCESS:", ok)
    print("WORLD:", world.snapshot())
    print("ROBOT:", robot)


if __name__ == "__main__":
    main()
