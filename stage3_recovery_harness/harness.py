from stage2_llm_harness.harness import Harness, extract_json
from stage2_llm_harness.llm_client import LLMConnectionError


def snapshot(ctx):
    return {
        "robot": {
            "left_hand": ctx.robot.left_hand,
            "right_hand": ctx.robot.right_hand,
        },
        "world": ctx.world.snapshot(),
    }


def classify_failure(skill_name, message):
    """문자열 실패를 Stage 3에서 사용할 간단한 코드로 바꾼다."""

    if "must be free" in message or "not empty" in message:
        code = "HAND_NOT_EMPTY"
        retryable = True
    elif "not holding" in message:
        code = "NOT_HOLDING_OBJECT"
        retryable = True
    elif "unknown object" in message:
        code = "OBJECT_NOT_FOUND"
        retryable = False
    else:
        code = "SKILL_FAILED"
        retryable = True

    return {
        "code": code,
        "skill": skill_name,
        "message": message,
        "retryable": retryable,
    }


def cap_goal_is_complete(ctx):
    """현재 Stage 3 예제의 최종 목표를 확인한다."""

    try:
        return ctx.world.get("pet").cap_open is True
    except KeyError:
        return False


class IntentionalFailurePlanner:
    """첫 계획만 일부러 실패시키고, 이후 계획은 실제 LLM에 맡긴다."""

    def __init__(self, llm_planner):
        self.llm_planner = llm_planner
        self.first_call = True

    def plan(self, command, skills, state=None, feedback=None):
        if self.first_call:
            self.first_call = False
            print("DEMO: 첫 계획은 복구 과정을 보여주기 위해 일부러 실패하게 만듭니다.")
            return [
                {"skill": "pick", "args": {"arm": "left", "object": "pet"}},
                {
                    "skill": "open_cap",
                    "args": {
                        "holder_arm": "left",
                        "worker_arm": "right",
                        "object": "pet",
                    },
                },
            ]

        print("LLM RECOVERY: 현재 상태와 실패 원인을 Qwen3에 전달합니다.")
        return self.llm_planner.plan(
            command,
            skills,
            state=state,
            feedback=feedback,
        )


class RecoveryHarness(Harness):
    """실패 상태를 관찰하고 LLM의 수정 계획을 실행한다."""

    def run_command(self, ctx, planner, command, max_replans=2, goal_checker=None):
        failure = None
        total_attempts = max_replans + 1

        for attempt in range(total_attempts):
            if attempt == 0:
                print("\n=== INITIAL PLAN ===")
            else:
                print("\n=== RECOVERY PLAN {} / {} ===".format(attempt, max_replans))

            current_state = snapshot(ctx)

            try:
                raw_plan = planner.plan(
                    command,
                    self.registry.schemas(),
                    state=current_state,
                    feedback=failure,
                )
                if isinstance(raw_plan, str):
                    raw_plan = extract_json(raw_plan)
                steps = self.validate_plan(raw_plan)
                if len(steps) == 0:
                    raise ValueError("plan is empty")
            except LLMConnectionError as error:
                print("HARNESS ABORT: Qwen3 connection failed: {}".format(error))
                return False
            except (ValueError, KeyError, TypeError) as error:
                failure = {
                    "code": "PLAN_REJECTED",
                    "skill": None,
                    "message": str(error),
                    "retryable": True,
                }
                print("PLAN FAILURE:", failure)
                if attempt == max_replans:
                    break
                continue

            print("PLAN:", steps)
            failure = None

            for index, step in enumerate(steps, start=1):
                skill_name = step["skill"]
                skill_args = step["args"]
                result = self.registry.call(skill_name, ctx, skill_args)
                print("[{}] {} {} -> {}: {}".format(
                    index,
                    skill_name,
                    skill_args,
                    result.status,
                    result.message,
                ))

                if not result.ok:
                    failure = classify_failure(skill_name, result.message)
                    print("EXECUTION FAILURE:", failure)
                    break

            if failure is None:
                if goal_checker is None or goal_checker(ctx):
                    print("GOAL CHECK: 목표가 달성되었습니다.")
                    return True

                failure = {
                    "code": "GOAL_NOT_REACHED",
                    "skill": None,
                    "message": "all steps succeeded, but the final goal is not reached",
                    "retryable": True,
                }
                print("GOAL CHECK FAILURE:", failure)

            if not failure["retryable"]:
                print("HARNESS ABORT: retry is not allowed for", failure["code"])
                return False

            if attempt < max_replans:
                print("REPLAN REQUEST: Qwen3가 실패를 복구할 새 계획을 만듭니다.")

        print("HARNESS ABORT: recovery budget exhausted")
        return False
