# Local LLM Robot Harness — Stages 0~8

CLI에서 단계별로 검증하는 방법은 [CLI_TEST_GUIDE.md](CLI_TEST_GUIDE.md)를 참고하세요.

Symbolic 단계에서 하네스의 핵심 구조를 먼저 익히고, 실제 MuJoCo IK에 같은 구조를
단계적으로 연결하는 교육용 프로젝트입니다.

## 설계 원칙

- LLM은 모터/관절 명령을 생성하지 않습니다.
- LLM은 **허용된 Robot Skill 이름 + 인자**만 계획합니다.
- Harness가 계획을 검증하고 Skill을 호출합니다.
- 로봇/환경의 실제 구현은 나중에 Symbolic → MuJoCo → Hardware adapter로 교체합니다.
- Stage 2에서는 고의로 retry를 넣지 않습니다. 실패 복구는 Stage 3의 학습 목표입니다.

## 폴더

```text
stage0_skill_api/         Skill 계약 자체를 이해 (자체 common 포함)
stage1_symbolic_robot/    상태만 존재하는 가상 로봇/월드 (자체 common 포함)
stage2_llm_harness/       LLM planner + validation + execution harness (자체 common 포함)
stage3_recovery_harness/  상태/실패 피드백 기반 재계획 (자체 common 포함)
stage4_mujoco_dual_arm/   MuJoCo 양팔 + PET/뚜껑/컵 환경
stage5_mujoco_ik/         JDCobot200 MuJoCo + Mink 5-DOF IK
stage6_contact_grasp/     MoveToSkill로 빨간 블록 접근·grasp·lift
stage7_llm_mujoco_harness/ Qwen 계획 검증 후 MuJoCo Skill 실행
stage8_retry_harness/     실패 피드백 기반 Qwen 재계획과 제한적 retry
```

Stage 0~2는 자기 폴더 안에 `common/skill_api.py`를 가집니다. 이후 단계는 학습할
변화가 잘 보이도록 바로 앞에서 확정한 작은 공개 경계만 재사용합니다. 실제 제품으로
통합하는 시점에는 안정된 계약을 최상위 공통 패키지로 합칠 수 있습니다.

## Stage 0 — Skill API

목표: `RobotSkill.execute(context, **args) -> SkillResult` 계약을 이해합니다.

```bash
cd local_llm_robot_harness_0_2
python3 -m stage0_skill_api.main
```

완료 기준:
- skill에 name/description/parameters가 있다.
- 실행 결과가 success/failure 등 구조화된 값으로 돌아온다.

## Stage 1 — Symbolic Robot

실제 좌표, 관절, 영상 없이 다음 상태만 다룹니다.

- 왼손/오른손이 무엇을 들고 있는가?
- PET는 어디에 있는가?
- PET 뚜껑은 열렸는가?

```bash
python3 -m stage1_symbolic_robot.main
```

여기서 `pick`, `place`, `open_cap` skill을 테스트합니다.

핵심은 `open_cap`이 단순 함수가 아니라 **precondition**을 가진다는 점입니다.
예: 한 팔이 PET를 잡아야 하고, 다른 팔은 비어 있어야 합니다.

## Stage 2 — LLM + Harness

먼저 LLM 없이 mock planner로 실행합니다.

```bash
python3 -m stage2_llm_harness.main
```

흐름:

```text
자연어 명령
   ↓
Planner(LLM)
   ↓ JSON plan
Harness
   ├─ 허용된 skill인가?
   ├─ step 수가 제한 안인가?
   ├─ JSON 구조가 맞는가?
   ↓
Robot Skill
   ↓
Symbolic Robot / World
```

### 로컬 LLM 연결

기본 설정은 `localhost:8080`에서 실행되는 llama.cpp의 Qwen3 8B입니다.

```bash
python3 -m stage2_llm_harness.main --llm \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

기본값을 명시하면 다음과 같습니다.

```bash
python3 -m stage2_llm_harness.main \
  --llm \
  --base-url http://127.0.0.1:8080/v1 \
  --model qwen3-8b \
  --provider openai \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

LLM이 반환해야 하는 예:

```json
[
  {"skill":"pick","args":{"arm":"left","object":"pet"}},
  {"skill":"open_cap","args":{"holder_arm":"left","worker_arm":"right","object":"pet"}}
]
```

## 왜 이 순서인가?

Stage 0~2에서 테스트하는 것은 로봇 제어 성능이 아니라 **책임 분리**입니다.

```text
LLM      : 무엇을 할지 계획
Harness  : 무엇이 허용되는지 통제, 실행 순서 관리
Skill    : 로봇이 할 수 있는 단위 기능
Backend  : Symbolic / MuJoCo / Real HW
```

따라서 Stage 4 이후 MuJoCo를 넣을 때 `pick()`의 내부 구현만 IK/접촉/카메라 기반으로 바꾸고, LLM-Harness 구조는 최대한 유지할 수 있습니다.

## Stage 3 — 실패 피드백과 재계획

Stage 2에서는 skill이 실패하면 즉시 종료합니다. Stage 3은 현재 로봇/월드 상태와 실패 이유를 Qwen에 돌려주고 제한된 횟수만 재계획합니다.

복구 과정을 눈으로 확인하는 데모는 오른손에 컵을 쥐게 한 뒤 첫 계획을 일부러
실패시킵니다. Qwen3는 `HAND_NOT_EMPTY`와 변경된 상태를 받고 컵을 내려놓은 후
뚜껑을 여는 수정 계획을 생성해야 합니다.

```bash
python3 -m stage3_recovery_harness.main --demo-recovery --model qwen3-8b \
  "PET 병을 왼팔로 잡고 오른팔로 뚜껑을 열어"
```

```text
SkillResult.FAILURE
      ↓
Failure Classifier
      ↓
retry 가능한가?
 ├─ yes → 상태/피드백을 LLM 또는 recovery policy에 제공 → 수정 계획
 └─ no  → abort / alarm
```

추천 failure code 예:
- OBJECT_NOT_FOUND
- GRASP_FAILED
- HAND_NOT_EMPTY
- CAP_NOT_OPENED
- IK_UNREACHABLE
- SENSOR_TIMEOUT

이 failure code가 나중에 MuJoCo와 실제 로봇에서도 동일하게 유지되는 것이 중요합니다.

## Stage 4~6 — MuJoCo와 IK Skill

Stage 4는 MuJoCo 장면과 시뮬레이션 루프를 소개하고, Stage 5는 실제 JDCobot200
모델에서 5-DOF IK를 실행합니다. Stage 6은 LLM 없이 고정된 task 순서와
`MoveToSkill`을 사용하여 빨간 블록을 잡고 들어 올립니다.

```bash
python3 -m stage4_mujoco_dual_arm.main
python3 -m stage5_mujoco_ik.main
python3 -m stage6_contact_grasp.main
```

Stage 5는 Stage 4를 import하지 않는 독립 package이며, `jdcobot200.xml`의 실제 mesh,
5개 arm joint와 `graspframe` TCP site를 사용합니다. 기본 reachable 목표 대신 xyz를
직접 지정할 수도 있습니다.

```bash
python3 -m stage5_mujoco_ik.main --target -0.05 -0.02 0.48
```

Stage 4는 `mujoco.viewer`가 아닌 GLFW 기반 렌더링 창을 직접 엽니다. 왼쪽 마우스로
회전, 오른쪽 마우스로 이동, 휠로 확대할 수 있고 ESC 또는 창 닫기로 종료됩니다.
일정 시간 후 자동 종료하거나 기존 headless 방식으로
실행하려면 다음 옵션을 사용합니다.

```bash
python3 -m stage4_mujoco_dual_arm.main --duration 10
python3 -m stage4_mujoco_dual_arm.main --headless
```

### Stage 6 — IK 지시로 빨간 블록 잡기

LLM이나 planner는 사용하지 않습니다. 사람이 작성한 고정 JSON 계획을 `Harness`가
allowlist와 각 Skill schema로 검증한 뒤 실행합니다. 계획에는 좌표 대신 객체 이름만
있고, `MoveToObjectSkill`이 MuJoCo에서 현재 좌표를 읽어 내부 `MoveToSkill`에 전달합니다.

```text
Harness: move_to_object(object="red_block")
→ MoveToObjectSkill: 객체 이름을 xyz로 변환
→ MoveToSkill: IK 이동
→ GraspSkill: actuator 폐쇄 + MuJoCo contact 확인 + weld 활성화
→ LiftSkill: weld로 결합된 블록과 TCP를 함께 이동
```

`MoveToSkill`, `MoveToObjectSkill`, `GraspSkill`, `LiftSkill`은 모두 `schema()`,
`validate_args()`, `execute(args)` 계약을 따릅니다. 빨간 블록은 자유 물체로 바닥에
놓이며, 접촉이 없으면 `GRASP_NO_CONTACT`로 실패합니다.

headless 실행:

```bash
python3 -m stage6_contact_grasp.main
```

viewer로 동작 확인:

```bash
python3 -m stage6_contact_grasp.main --viewer --duration 10
```

### Stage 7 — Qwen 계획으로 MuJoCo 로봇 동작시키기

Stage 6의 고정 계획 대신 Qwen3-8B가 자연어 명령을 JSON Skill 계획으로 만듭니다.
Qwen에는 `move_to_object`, `grasp`, `lift` schema와 현재 MuJoCo 상태만 전달됩니다.
저수준 `move_to`와 xyz 좌표는 노출하지 않습니다.

```text
자연어 명령 → Qwen3-8B → JSON plan → Harness 검증
→ 허용된 Skill 실행 → IK/접촉/weld → MuJoCo 결과 및 goal 확인
```

llama.cpp가 `localhost:8080`에서 실행 중일 때:

```bash
python3 -m stage7_llm_mujoco_harness.main \
  "빨간 블록을 집어서 들어 올려 주세요"
```

viewer로 확인:

```bash
python3 -m stage7_llm_mujoco_harness.main --viewer --duration 10 \
  "빨간 블록을 집어서 들어 올려 주세요"
```

다른 endpoint를 쓰면 `--base-url`, `--model`, `--provider`로 지정합니다. LLM이
허용되지 않은 Skill이나 잘못된 인자를 만들면 로봇을 움직이기 전에
`PLAN_REJECTED`가 반환됩니다.

### Stage 8 — Try, fail, Qwen replan, retry

한 번의 LLM 계획에 재시도 sequence를 미리 하드코딩하지 않습니다. Harness가 Skill
실패를 감지하면 실패 코드, 완료된 Skill, 이전 계획과 최신 MuJoCo 상태를 Qwen에 다시
전달합니다. Qwen이 수정 계획을 만들고 Harness가 이를 다시 검증·실행합니다.

```text
Qwen plan → Harness 실행 → Skill 실패
    ↑                         ↓
    └── 실패 정보 + 최신 상태 ──┘
```

성공은 `held_object` 문자열만으로 판정하지 않습니다. 블록의 실제 높이가 2cm 이상
증가했고 TCP에서 5cm 이내에 유지되는지도 확인합니다. contact 순간의 현재 상대 자세를
weld constraint에 기록하므로 블록이 XML 초기 자세로 튀는 현상을 방지합니다. 이
사후조건이 실패하면 `GOAL_NOT_REACHED`를 Qwen에 전달해 다시 계획합니다.

재시도 여부를 자연어 명령에 적을 수는 있지만, 안전 한도는 LLM이 아니라 Harness의
`--max-retries`가 강제합니다. 허용 범위는 0~3회입니다.

실제 오류가 발생할 때만 재계획하려면:

```bash
python3 -m stage8_retry_harness.main --max-retries 2 \
  "빨간 블록을 들어 올려 주세요. 실패하면 원인에 맞게 다시 계획하세요"
```

첫 grasp를 의도적으로 한 번 실패시켜 전체 복구 흐름을 확인하려면:

```bash
python3 -m stage8_retry_harness.main --demo-failure --viewer --duration 10 \
  "빨간 블록을 들어 올려 주세요. 실패하면 원인에 맞게 다시 계획하세요"
```

## 전체 테스트

```bash
python3 -m unittest discover -v
```
