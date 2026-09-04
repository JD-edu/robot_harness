"""Stage 7의 Qwen3-8B Planner 경계."""

from stage2_llm_harness.harness import extract_json
from stage2_llm_harness.llm_client import LocalLLMPlanner


class QwenSkillPlanner:
    """자연어 명령과 Skill schema를 Qwen에 보내 JSON 계획만 반환한다."""

    def __init__(self, base_url="http://127.0.0.1:8080/v1", model="qwen3-8b",
                 provider="auto", timeout=120.0):
        self.client = LocalLLMPlanner(
            base_url=base_url,
            model=model,
            provider=provider,
            timeout=timeout,
        )
        self.last_raw_response = None

    def plan(self, command, skill_schemas, state, feedback=None):
        planner_command = (
            command
            + "\n완료에 필요한 전체 순서를 계획하세요. "
              "허용된 skill만 사용하고 모터, 관절값, xyz 좌표를 직접 만들지 마세요."
        )
        raw = self.client.plan(
            planner_command,
            skill_schemas,
            state=state,
            feedback=feedback,
        )
        print(f"LLM raw answer: {raw}")
        self.last_raw_response = raw
        return extract_json(raw) if isinstance(raw, str) else raw
