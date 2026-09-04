import json

try:
    from stage2_llm_harness.common.skill_api import SkillResult, SkillStatus
except ModuleNotFoundError:
    from common.skill_api import SkillResult, SkillStatus


class SkillRegistry:
    """허용된 Skill을 이름으로 찾아주는 목록."""

    def __init__(self, skills):
        self.skills = {}
        for skill in skills:
            self.skills[skill.name] = skill

    def schemas(self):
        result = []
        for skill in self.skills.values():
            result.append(skill.schema())
            print(f"skills schema: {skill.schema()}")
        return result

    def call(self, name, ctx, args):
        if name not in self.skills:
            return SkillResult(SkillStatus.REJECTED, "skill not allowed: " + name)

        skill = self.skills[name]
        try:
            skill.validate_args(args)
            return skill.execute(ctx, **args)
        except (KeyError, ValueError, TypeError) as error:
            return SkillResult(SkillStatus.FAILURE, str(error))


class Harness:
    """LLM 계획을 검사한 다음 Skill을 순서대로 실행한다."""

    def __init__(self, registry, max_steps=8):
        self.registry = registry
        self.max_steps = max_steps

    def validate_plan(self, raw_plan):
        if not isinstance(raw_plan, list):
            raise ValueError("plan must be a JSON list")
        if len(raw_plan) > self.max_steps:
            raise ValueError("plan exceeds max_steps={}".format(self.max_steps))

        checked_steps = []

        for index, item in enumerate(raw_plan):
            if not isinstance(item, dict):
                raise ValueError("step {}: step must be object".format(index))
            if set(item.keys()) != {"skill", "args"}:
                raise ValueError("step {}: use exactly skill,args".format(index))

            skill_name = item["skill"]
            skill_args = item["args"]

            if skill_name not in self.registry.skills:
                raise ValueError("step {}: unknown skill {}".format(index, skill_name))
            if not isinstance(skill_args, dict):
                raise ValueError("step {}: args must be object".format(index))

            self.registry.skills[skill_name].validate_args(skill_args)
            checked_steps.append({"skill": skill_name, "args": skill_args})

        print(f"checked_steps : {checked_steps}")
        return checked_steps

    def run(self, ctx, raw_plan):
        steps = self.validate_plan(raw_plan)

        for index, step in enumerate(steps, start=1):
            result = self.registry.call(step["skill"], ctx, step["args"])
            print("[{}] {} {} -> {}: {}".format(
                index, step["skill"], step["args"], result.status, result.message
            ))

            if not result.ok:
                print("HARNESS STOP: failure is not retried in stage 2")
                return False

        return True


def extract_json(text):
    """Qwen 응답에서 JSON 부분을 찾는다."""

    text = text.strip()

    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()

    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:].lstrip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(text):
            if character in "[{":
                try:
                    value, unused_end = decoder.raw_decode(text[index:])
                    return value
                except json.JSONDecodeError:
                    pass

    raise ValueError("LLM response does not contain valid JSON")
