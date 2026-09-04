import argparse

from stage3_recovery_harness.common.skill_api import SkillContext
from stage2_llm_harness.skills import OpenCapSkill, PickSkill, PlaceSkill
from stage2_llm_harness.harness import SkillRegistry
from stage2_llm_harness.llm_client import LocalLLMPlanner
from stage2_llm_harness.main import build_world
from stage3_recovery_harness.harness import (
    IntentionalFailurePlanner,
    RecoveryHarness,
    cap_goal_is_complete,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="qwen3-8b")
    parser.add_argument("--provider", choices=("auto", "ollama", "openai"), default="auto")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-replans", type=int, default=2)
    parser.add_argument(
        "--demo-recovery",
        action="store_true",
        help="force the first plan to fail, then let Qwen3 recover",
    )
    args = parser.parse_args()

    robot, world = build_world()
    ctx = SkillContext(robot=robot, world=world)
    registry = SkillRegistry([PickSkill(), PlaceSkill(), OpenCapSkill()])
    planner = LocalLLMPlanner(args.base_url, args.model, args.provider, args.timeout)

    if args.demo_recovery:
        # 오른손이 컵을 들고 있으므로 첫 open_cap은 HAND_NOT_EMPTY로 실패한다.
        robot.set_held("right", "cup")
        cup = world.get("cup")
        cup.held_by = "right"
        cup.location = "held"
        planner = IntentionalFailurePlanner(planner)
        print("DEMO SETUP: right hand is holding cup")

    ok = RecoveryHarness(registry).run_command(
        ctx,
        planner,
        args.command,
        args.max_replans,
        goal_checker=cap_goal_is_complete,
    )
    print("SUCCESS:", ok)
    print("WORLD:", world.snapshot())
    print("ROBOT:", robot)


if __name__ == "__main__":
    main()
