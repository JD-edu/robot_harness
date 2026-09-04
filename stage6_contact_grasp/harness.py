"""LLM 없이도 계획 경계를 연습하는 Stage 6 Skill Registry와 Harness."""


class SkillRegistry:
    def __init__(self, skills):
        self.skills = {skill.name: skill for skill in skills}

    def schemas(self):
        return [skill.schema() for skill in self.skills.values()]

    def get(self, name):
        if name not in self.skills:
            raise ValueError("skill is not allowed: " + str(name))
        return self.skills[name]


class Harness:
    def __init__(self, registry, max_steps=4):
        self.registry = registry
        self.max_steps = int(max_steps)

    def validate_plan(self, plan):
        if not isinstance(plan, list) or not 1 <= len(plan) <= self.max_steps:
            raise ValueError("plan must be a non-empty list within max_steps")
        for index, step in enumerate(plan):
            if not isinstance(step, dict) or set(step) != {"skill", "args"}:
                raise ValueError(f"step {index}: use exactly skill and args")
            self.registry.get(step["skill"]).validate_args(step["args"])
        return plan

    def run(self, plan):
        events = []
        for step in self.validate_plan(plan):
            result = self.registry.get(step["skill"]).execute(step["args"])
            events.append({"skill": step["skill"], "args": step["args"], "result": result})
            if not result["ok"]:
                return {"ok": False, "failure": result, "events": events}
        return {"ok": True, "events": events}
