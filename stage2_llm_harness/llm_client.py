import json
import urllib.error
import urllib.request


SYSTEM_PROMPT = """You are a robot task planner.
Never control motors directly. Return ONLY a JSON list, without explanations.
Each item must be exactly {\"skill\": <allowed skill name>, \"args\": {...}}.
Use only supplied skills and exact argument names. Keep the plan short.
The current state is authoritative; do not repeat an already completed action.
For object arguments, use an exact key from current_state.world (for example \"pet\"),
never a description, kind, translation, or invented name.
"""


class LLMConnectionError(RuntimeError):
    pass


class MockPlanner:
    """LLM 없이 Harness를 연습하기 위한 가짜 Planner."""

    def plan(self, command, skills, **extra):
        if "뚜껑" in command or "cap" in command.lower():
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
        return []


class LocalLLMPlanner:
    """llama.cpp 또는 Ollama에 HTTP 요청을 보내는 Planner."""

    def __init__(
        self,
        base_url="http://127.0.0.1:8080/v1",
        model="qwen3-8b",
        provider="auto",
        timeout=120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        if provider not in ("auto", "ollama", "openai"):
            raise ValueError("provider must be auto, ollama, or openai")

        if provider == "auto":
            if self.base_url.endswith("/v1"):
                self.provider = "openai"
            else:
                self.provider = "ollama"
        else:
            self.provider = provider

    def post(self, path, body):
        url = self.base_url + path
        request_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        request = urllib.request.Request(url, data=request_body, headers=headers)

        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            response_text = response.read().decode("utf-8")
            response.close()
            return json.loads(response_text)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            message = "local LLM request failed ({}, model={}): {}".format(
                self.base_url, self.model, error
            )
            raise LLMConnectionError(message)

    def plan(self, command, skills, state=None, feedback=None):
        user_data = {
            "allowed_skills": skills,
            "current_state": state or {},
            "previous_failure": feedback,
            "user_command": command,
        }
        print(f"allowed skills: {skills}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(user_data, ensure_ascii=False, indent=2),
            },
        ]

        if self.provider == "ollama":
            body = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"temperature": 0, "num_predict": 1024},
            }
            data = self.post("/api/chat", body)
            return data["message"]["content"]

        body = {
            "model": self.model,
            "temperature": 0,
            "messages": messages,
        }
        #print(f"SYSTEM_PROMPT: {SYSTEM_PROMPT}")
        data = self.post("/chat/completions", body)
        return data["choices"][0]["message"]["content"]


# 이전 Stage 2 코드에서 사용한 이름도 계속 쓸 수 있게 한다.
OpenAICompatiblePlanner = LocalLLMPlanner
