"""Planner가 만든 계획을 Harness로 실행하는 Stage 2 예제입니다."""

import argparse

try:
    from stage2_llm_harness.common.skill_api import SkillContext
    from stage2_llm_harness.harness import Harness, SkillRegistry, extract_json
    from stage2_llm_harness.llm_client import LocalLLMPlanner, MockPlanner
    from stage2_llm_harness.skills import OpenCapSkill, PickSkill, PlaceSkill
    from stage2_llm_harness.symbolic_robot import (
        ObjectState,
        SymbolicRobot,
        SymbolicWorld,
    )
except ModuleNotFoundError:
    from common.skill_api import SkillContext
    from harness import Harness, SkillRegistry, extract_json
    from llm_client import LocalLLMPlanner, MockPlanner
    from skills import OpenCapSkill, PickSkill, PlaceSkill
    from symbolic_robot import ObjectState, SymbolicRobot, SymbolicWorld


def build_world():
    robot = SymbolicRobot()

    world = SymbolicWorld()
    world.add(ObjectState("pet", "pet_bottle", "table"))
    world.add(ObjectState("cup", "cup", "table"))

    return robot, world


def read_options():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        default="PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어",
    )
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="qwen3-8b")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--timeout", type=float, default=120)
    return parser.parse_args()


def main():
    options = read_options()

    robot, world = build_world()
    context = SkillContext(robot, world)

    allowed_skills = [PickSkill(), PlaceSkill(), OpenCapSkill()]
    registry = SkillRegistry(allowed_skills)
    harness = Harness(registry)

    # 기본 실행에서는 이해하기 쉬운 가짜 Planner를 사용합니다.
    # --llm 옵션을 주었을 때만 실제 로컬 LLM에 접속합니다.
    if options.llm:
        planner = LocalLLMPlanner(
            options.base_url,
            options.model,
            options.provider,
            options.timeout,
        )
    else:
        planner = MockPlanner()

    current_state = {
        "robot": robot.snapshot(),
        "world": world.snapshot(),
    }

    print("사용자 명령:", options.command)

    plan = planner.plan(
        options.command,
        registry.schemas(),
        state=current_state,
    )

    # 실제 LLM은 JSON 문자열을 반환합니다.
    # MockPlanner는 이미 Python 리스트를 반환합니다.
    if isinstance(plan, str):
        plan = extract_json(plan)

    print("계획:", plan)

    success = harness.run(context, plan)

    print("성공:", success)
    print("WORLD:", world.snapshot())
    print("ROBOT:", robot.snapshot())


if __name__ == "__main__":
    main()
