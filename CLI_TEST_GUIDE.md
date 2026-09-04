# Robot Harness CLI 테스트 가이드

이 문서는 `localhost:8080`에서 실행 중인 **llama.cpp + Qwen3 8B**를 사용하여 Robot Harness의 Stage 0~3을 CLI에서 검증하는 방법을 설명합니다.

## 0. CLI 명령 읽는 방법

CLI는 터미널에 글자로 명령을 입력하는 방식입니다. 이 문서의 명령은 한꺼번에 전부 붙여 넣지 말고, 처음에는 한 명령씩 실행하는 것이 좋습니다.

### `python3 -m stage0_skill_api.main`의 의미

프로젝트의 실제 파일 위치는 다음과 같습니다.

```text
stage0_skill_api/main.py
```

Python에서는 `/` 대신 `.`을 사용하여 다음과 같이 모듈 경로를 표현할 수 있습니다.

```text
stage0_skill_api.main
```

따라서 다음 명령은 `stage0_skill_api/main.py`를 실행한다는 뜻입니다.

```bash
python3 -m stage0_skill_api.main
```

Stage 0 폴더 안으로 직접 이동한 경우에는 다음 명령도 사용할 수 있습니다.

```bash
cd /home/robo/robot_harness/stage0_skill_api
python3 main.py
```

Stage 0의 `main.py`는 위 두 실행 방식을 모두 지원합니다.

각 부분의 의미는 다음과 같습니다.

| 표현 | 의미 |
|---|---|
| `python3` | Python 3 실행 프로그램 |
| `-m` | 파일을 Python 모듈 경로로 실행 |
| `stage0_skill_api` | 코드가 들어 있는 폴더 |
| `main` | `main.py` 파일 |
| `stage0_skill_api.main` | `stage0_skill_api/main.py` |

이 프로젝트에서는 다른 폴더의 코드를 안정적으로 불러오기 위해 프로젝트 루트에서 `python3 -m ...` 방식을 사용합니다.

### 줄 끝의 `\` 기호

다음 명령의 `\`는 명령이 다음 줄로 이어진다는 뜻입니다.

```bash
python3 -m stage2_llm_harness.main --llm \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

위 명령은 아래 한 줄짜리 명령과 같습니다.

```bash
python3 -m stage2_llm_harness.main --llm "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

처음에는 한 줄짜리 형태를 사용하는 편이 이해하기 쉽습니다.

### 따옴표의 의미

```text
"PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

따옴표는 공백이 들어간 전체 문장을 하나의 입력값으로 묶습니다. 따옴표가 없으면 터미널이 각 단어를 서로 다른 입력값으로 처리할 수 있습니다.

## 1. 사전 조건

- Python 3가 설치되어 있어야 합니다.
- llama.cpp 서버가 `http://127.0.0.1:8080`에서 실행 중이어야 합니다.
- 서버가 노출하는 모델 ID는 `qwen3-8b`여야 합니다.
- 모든 명령은 프로젝트 루트에서 실행합니다.

```bash
cd /home/robo/robot_harness
python3 --version
```

이 프로젝트는 Python 표준 라이브러리만 사용하므로 별도의 `pip install`은 필요하지 않습니다.

## 2. llama.cpp 서버 확인

### 2.1 모델 목록 확인

```bash
curl -fsS http://127.0.0.1:8080/v1/models
```

응답의 `data` 배열에 다음과 같은 모델 ID가 있어야 합니다.

```json
{
  "id": "qwen3-8b"
}
```

### 2.2 Chat Completions 직접 확인

```bash
curl -fsS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3-8b",
    "temperature": 0,
    "messages": [
      {"role": "user", "content": "JSON으로 {\"status\":\"ok\"}만 출력해"}
    ]
  }'
```

HTTP 연결 오류 없이 `choices[0].message.content`가 반환되면 서버를 사용할 수 있습니다.

## 3. 자동 테스트

전체 회귀 테스트를 실행합니다.

```bash
python3 -m unittest discover -v
```

정상 결과:

```text
Ran 5 tests

OK
```

이 테스트는 다음 항목을 검사합니다.

- Qwen의 `<think>...</think>` 및 Markdown JSON 응답 처리
- 허용되지 않은 팔 이름 차단
- 정확한 월드 객체 ID 사용 지침
- 정상적인 `pick → open_cap` 실행
- 잘못된 계획 이후 Stage 3 재계획

## 4. Stage 0 — Skill API 테스트

```bash
python3 -m stage0_skill_api.main
```

정상 결과에는 다음 내용이 포함됩니다.

```text
ROBOT: Skill API ready
SkillResult(success=True, message='message printed', ...)
```

이 단계는 LLM이나 llama.cpp 서버를 사용하지 않습니다.

Stage 0에서는 다음과 같은 일반 Python 문법을 확인합니다.

- `class`로 Skill 만들기
- `def`로 함수 만들기
- `__init__`으로 값 저장하기
- 딕셔너리에 결과 담기
- `print()`로 결과 출력하기

Stage별 공통 계약은 다른 단계와 공유하지 않고 다음 위치에 있습니다.

```text
stage0_skill_api/common/skill_api.py
```

## 5. Stage 1 — Symbolic Robot 테스트

```bash
python3 -m stage1_symbolic_robot.main
```

예상 실행 순서:

```text
pick: success
open_cap: success
place: success
```

최종 상태에서 `pet.cap_open`은 `True`이고 양손은 비어 있어야 합니다.

Stage 1은 `dataclass`나 `Enum` 없이 일반 클래스와 다음 기초 문법으로 작성되어 있습니다.

- 객체 생성과 속성 사용
- `if` 조건문
- `for` 반복문
- 리스트와 딕셔너리
- `None`으로 빈손 표현

Stage 1의 계약은 Stage 0 파일을 불러오지 않고 다음 파일에 별도로 정의되어 있습니다.

```text
stage1_symbolic_robot/common/skill_api.py
```

## 6. Stage 2 — Mock Planner 테스트

LLM 연결 없이 Harness의 계획 검증과 Skill 실행만 테스트합니다.

```bash
python3 -m stage2_llm_harness.main \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

정상 결과:

```text
PLAN: [{'skill': 'pick', ...}, {'skill': 'open_cap', ...}]
[1] pick ... -> success
[2] open_cap ... -> success
SUCCESS: True
```

Stage 2에서도 LLM 계획을 별도 고급 객체로 바꾸지 않고 다음과 같은 평범한 리스트와 딕셔너리로 처리합니다.

Stage 2 역시 자체 `common/skill_api.py`, `symbolic_robot.py`, `skills.py`를 가지고 있으므로 Stage 1의 내부 코드에 의존하지 않습니다.

Stage 2도 다음 두 실행 방식을 모두 지원합니다.

프로젝트 루트에서 모듈로 실행:

```bash
cd /home/robo/robot_harness
python3 -m stage2_llm_harness.main --llm "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

Stage 2 폴더에서 파일로 직접 실행:

```bash
cd /home/robo/robot_harness/stage2_llm_harness
python3 main.py --llm "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

주의: Stage 2 폴더 안에서는 `python3 -m stage2_llm_harness.main`을 사용하지 않습니다.
`-m stage2_llm_harness.main`은 상위 폴더에서 `stage2_llm_harness`를 찾기 때문입니다.

```python
plan = [
    {
        "skill": "pick",
        "args": {
            "arm": "left",
            "object": "pet"
        }
    }
]
```

Harness는 `for` 반복문으로 각 단계를 꺼내 실행합니다.

```python
for step in plan:
    skill_name = step["skill"]
    skill_args = step["args"]
```

## 7. Stage 2 — Qwen3 8B 통합 테스트

현재 프로젝트의 기본값은 다음과 같습니다.

```text
Base URL: http://127.0.0.1:8080/v1
Model:    qwen3-8b
Provider: auto → openai
Timeout:  120초
```

따라서 다음 명령만으로 실제 Qwen3를 호출할 수 있습니다.

```bash
python3 -m stage2_llm_harness.main --llm \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

정상 결과의 핵심 부분:

```text
PLAN: [
  {'skill': 'pick', 'args': {'arm': 'left', 'object': 'pet'}},
  {'skill': 'open_cap', 'args': {
    'holder_arm': 'left',
    'worker_arm': 'right',
    'object': 'pet'
  }}
]
[1] pick ... -> success
[2] open_cap ... -> success
SUCCESS: True
```

Qwen이 허용되지 않은 Skill 또는 잘못된 인자를 반환하면 Harness가 실행 전에 계획을 거부합니다. Skill 실행 중 실패하면 Stage 2는 즉시 중단하며 재시도하지 않습니다.

### 설정을 명시하여 실행

```bash
python3 -m stage2_llm_harness.main \
  --llm \
  --base-url http://127.0.0.1:8080/v1 \
  --model qwen3-8b \
  --provider openai \
  --timeout 120 \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

## 8. Stage 3 — 실패 복구 및 재계획 테스트

Stage 3은 현재 로봇 상태, 월드 상태와 이전 실패 원인을 Qwen에 전달하여 수정된 계획을 요청합니다.

다음 데모가 Stage 3의 핵심 테스트입니다.

```bash
cd /home/robo/robot_harness
python3 -m stage3_recovery_harness.main --demo-recovery \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

`--demo-recovery`는 다음 상황을 의도적으로 만듭니다.

```text
1. 오른손이 cup을 들고 시작
2. 왼손으로 pet을 집음
3. 오른손으로 뚜껑 열기 시도
4. HAND_NOT_EMPTY 실패
5. 현재 상태와 실패 코드를 Qwen3에 전달
6. Qwen3가 복구 계획 생성
7. 예상 복구: place(right, table) → open_cap(...)
8. pet.cap_open 값으로 최종 목표 확인
```

출력에서 `EXECUTION FAILURE`, `LLM RECOVERY`, `RECOVERY PLAN`,
`GOAL CHECK` 순서를 확인합니다.

```bash
python3 -m stage3_recovery_harness.main \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

재계획 횟수를 직접 지정할 수도 있습니다.

```bash
python3 -m stage3_recovery_harness.main \
  --max-replans 2 \
  --timeout 120 \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

계획 또는 Skill이 실패하면 다음과 같은 메시지가 출력됩니다.

```text
REPLAN 1: plan rejected: ...
```

복구 예산을 모두 사용하면 안전하게 중단합니다.

```text
HARNESS ABORT: recovery budget exhausted
SUCCESS: False
```

## 9. 추가 명령 테스트

현재 Symbolic World에 등록된 객체 ID는 다음과 같습니다.

- `pet`: PET 병
- `cup`: 컵

등록되지 않은 객체를 요청하면 Qwen이 계획을 생성하더라도 Skill 실행 단계에서 거부될 수 있습니다.

```bash
python3 -m stage2_llm_harness.main --llm \
  "컵을 오른팔로 집어"
```

현재 Skill 목록:

- `pick(arm, object)`
- `place(arm, location)`
- `open_cap(holder_arm, worker_arm, object)`

## 10. 문제 해결

### Connection refused

```text
local LLM request failed ... Connection refused
```

llama.cpp 서버와 포트를 확인합니다.

```bash
curl -v http://127.0.0.1:8080/v1/models
```

### 모델을 찾을 수 없음

`/v1/models` 응답에서 실제 모델 ID를 확인하고 `--model`로 전달합니다.

```bash
python3 -m stage2_llm_harness.main \
  --llm \
  --model 실제_모델_ID \
  "PET 병의 뚜껑을 열어"
```

### 응답 시간 초과

CPU 추론이나 긴 컨텍스트 때문에 120초 이상 걸리면 제한 시간을 늘립니다.

```bash
python3 -m stage2_llm_harness.main \
  --llm \
  --timeout 300 \
  "PET 병의 뚜껑을 열어"
```

### JSON 계획 오류

Qwen 응답이 유효한 JSON 계획을 포함하지 않으면 다음과 같이 거부됩니다.

```text
LLM response does not contain valid JSON
```

Stage 3에서는 이 오류를 실패 피드백으로 전달하여 제한된 횟수만 재계획합니다.

### `python` 명령을 찾을 수 없음

이 환경에서는 `python` 대신 `python3`를 사용합니다.

```bash
python3 --version
```

### `No module named 'stage0_skill_api'`

파일을 직접 실행할 때 프로젝트 루트를 Python이 찾지 못하면 발생하는 오류입니다.
현재 코드는 다음 두 방식을 모두 지원하도록 구성되어 있습니다.

프로젝트 루트에서 모듈로 실행:

```bash
cd /home/robo/robot_harness
python3 -m stage0_skill_api.main
```

Stage 0 폴더에서 파일로 실행:

```bash
cd /home/robo/robot_harness/stage0_skill_api
python3 main.py
```

## 11. 권장 테스트 순서

처음 학습할 때는 아래 명령을 한 줄씩 실행하고, 각 결과를 확인한 후 다음 줄로 넘어가세요.

가장 간단한 시작 순서는 다음 세 명령입니다.

```bash
cd /home/robo/robot_harness
python3 -m stage0_skill_api.main
python3 -m stage1_symbolic_robot.main
```

Stage 0과 Stage 1을 이해한 다음 전체 테스트를 진행합니다.

```bash
cd /home/robo/robot_harness
curl -fsS http://127.0.0.1:8080/v1/models
python3 -m unittest discover -v
python3 -m stage0_skill_api.main
python3 -m stage1_symbolic_robot.main
python3 -m stage2_llm_harness.main
python3 -m stage2_llm_harness.main --llm \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
python3 -m stage3_recovery_harness.main \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```
