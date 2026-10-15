"""LLM의 계획을 검사하고 Skill을 실행하는 Harness입니다."""

import json

try:
    from stage2_llm_harness.common.skill_api import SkillResult, SkillStatus
except ModuleNotFoundError:
    from common.skill_api import SkillResult, SkillStatus


class SkillRegistry:
    """LLM이 사용해도 되는 Skill들을 이름으로 보관합니다."""

    def __init__(self, skills):
        self.skills = {}

        for skill in skills:
            self.skills[skill.name] = skill

    def schemas(self):
        """Planner에게 전달할 Skill 설명 목록을 만듭니다."""

        result = []

        for skill in self.skills.values():
            result.append(skill.schema())

        return result

    def call(self, name, context, args):
        """이름으로 Skill을 찾아서 실행합니다."""

        if name not in self.skills:
            return SkillResult(
                SkillStatus.REJECTED,
                "허용되지 않은 Skill입니다: " + name,
            )

        skill = self.skills[name]

        try:
            skill.validate_args(args)
            return skill.execute(context, **args)
        except (KeyError, ValueError, TypeError) as error:
            return SkillResult(SkillStatus.FAILURE, str(error))


class Harness:
    """계획 전체를 먼저 검사한 후 Skill을 순서대로 실행합니다."""

    def __init__(self, registry, max_steps=8):
        self.registry = registry
        self.max_steps = max_steps

    def validate_plan(self, plan):
        if not isinstance(plan, list):
            raise ValueError("계획은 리스트여야 합니다")
        if len(plan) > self.max_steps:
            raise ValueError("계획의 단계가 너무 많습니다")

        checked_steps = []

        for step in plan:
            if not isinstance(step, dict):
                raise ValueError("계획의 각 단계는 딕셔너리여야 합니다")
            if "skill" not in step or "args" not in step:
                raise ValueError("각 단계에는 skill과 args가 필요합니다")
            if len(step) != 2:
                raise ValueError("각 단계에는 skill과 args만 사용할 수 있습니다")

            skill_name = step["skill"]
            skill_args = step["args"]

            if skill_name not in self.registry.skills:
                raise ValueError("알 수 없는 Skill입니다: " + str(skill_name))

            skill = self.registry.skills[skill_name]
            skill.validate_args(skill_args)

            checked_steps.append(step)

        return checked_steps

    def run(self, context, plan):
        checked_steps = self.validate_plan(plan)
        step_number = 1

        for step in checked_steps:
            skill_name = step["skill"]
            skill_args = step["args"]
            result = self.registry.call(skill_name, context, skill_args)

            print(
                "[{}] {} -> {}: {}".format(
                    step_number,
                    skill_name,
                    result.status,
                    result.message,
                )
            )

            if result.ok is False:
                print("Skill이 실패했으므로 Harness를 멈춥니다.")
                return False

            step_number = step_number + 1

        return True


def extract_json(text):
    """LLM이 반환한 JSON 문자열을 Python 리스트로 바꿉니다."""

    text = text.strip()

    # 추론 내용을 함께 출력하는 모델에서는 </think> 뒤의 내용만 사용합니다.
    if "</think>" in text:
        parts = text.split("</think>", 1)
        text = parts[1].strip()

    # 일부 LLM은 JSON을 Markdown 코드 블록 안에 넣어서 반환합니다.
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        raise ValueError("LLM 응답이 올바른 JSON이 아닙니다")
