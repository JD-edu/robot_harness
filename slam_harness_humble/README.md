# Qwen3 + Three Tables 하네스 실행

ROS 2 Humble·Gazebo Classic 환경에서 다음 순서로 실행합니다.
각 단계는 **별도 터미널**을 사용하며, 서버·게이트·시뮬레이션 터미널은 실행한 채 유지합니다.

```text
1. Qwen3 LLM 서버 → 2. 속도 게이트 → 3. Three Tables 시뮬레이션·SLAM·Nav2·RViz → 4. Python 하네스
```

## 실행 전 준비

처음 실행하거나 ROS 런치 파일이 변경되었을 때 빌드합니다.

```bash
cd /home/robo/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select ros_dd_description ros_dd_gazebo ros_dd_cartographer ros_dd_navigation
```

아래 ROS 터미널은 모두 `ROS_DOMAIN_ID=0`을 사용합니다.
다른 값을 사용한다면 게이트·시뮬레이션·하네스 터미널에서 같은 값으로 바꾸세요.
동일한 시뮬레이션과 속도 게이트는 각각 하나만 실행합니다.

## 1. LLM 서버 시작 — 터미널 A

```bash
cd /home/robo/local_LLM/Qwen3-8b
./start-server.sh --chat-template-kwargs '{"enable_thinking":false}'
```

(미리 아래 설명에 맞게 Qwen3 8B 및 llama.cpp를 설치해서 로컬 LLM이 동작하도록 셋팅이 되어있어야 합니다.)   
서버 주소는 `http://127.0.0.1:8080/v1`, 모델 이름은 `qwen3-8b`입니다.
모델 로딩이 끝날 때까지 기다립니다. 해당 주소에 서버가 이미 실행 중이면 그대로 사용합니다.
다른 터미널에서 다음 명령으로 상태를 확인할 수 있습니다.

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/v1/models
```

`/health`가 정상이고 모델 목록에 `qwen3-8b`가 있어야 합니다.
LLM은 자연어를 방문·재시도·실패 분기 계획으로 변환합니다. 좌표와 주행 속도는 생성하지 않습니다.

## 2. Velocity 서비스 시작 — 터미널 B

```bash
source /opt/ros/humble/setup.bash
source /home/robo/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=0
cd /home/robo/robot_harness

python3 -m slam_harness_humble.velocity_gate \
  --ros-args -p use_sim_time:=true
```

이 명령은 `slam_velocity_gate` 노드를 실행하고
`/slam_harness/fine_control` 서비스를 제공합니다.
아직 Gazebo가 실행되지 않았다면 센서와 시계가 없으므로 정지 출력을 내며 대기합니다.

### 이 서비스를 먼저 실행하는 이유

Nav2의 일반 주행과 하네스의 미세 정렬·후퇴는 서로 다른 속도 명령을 만듭니다.
게이트는 사용할 속도 하나를 선택하여 Gazebo 로봇의 `/cmd_vel`로 전달합니다.

```text
Nav2 ─ /slam_harness/nav_cmd_vel ───┐
                                   ├─ velocity_gate ─ /cmd_vel ─ Gazebo 로봇
미세 정렬·후퇴 ─ fine_cmd_vel ───────┘
```

| 서비스 요청 | 선택하는 제어 |
| --- | --- |
| `data: false` | Nav2 일반 주행 |
| `data: true` | 하네스의 미세 정렬·후퇴 |

게이트는 미세 제어 모드로 시작합니다. 하네스는 이동 전에 Nav2 모드로 전환하고,
미세 정렬·후퇴 또는 미션 종료 시 미세 제어 모드로 전환합니다.
따라서 하네스 미션 실행 시 별도의 수동 서비스 호출은 필요하지 않습니다.

게이트가 없으면 하네스가 제어권을 선택할 수 없어 `gate_unavailable`로 이동을 중단합니다.
게이트는 최대 속도 제한, 라이다·TF 검사, 오래된 센서·속도 명령에 대한 정지도 담당합니다.
모드 전환은 이 검사나 속도 제한을 해제하는 동작이 아닙니다.

## 3. Three Tables 런치 시작 — 터미널 C

```bash
source /opt/ros/humble/setup.bash
source /home/robo/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=0

ros2 launch ros_dd_navigation three_tables_navigation.launch.py \
  gui:=true use_rviz:=true use_sim_time:=true use_velocity_gate:=false
```

`use_velocity_gate:=false`는 터미널 B의 게이트를 사용하기 위해 런치 내부 게이트 실행을 끕니다.
게이트를 중복 실행하지 마세요.

이 런치는 다음을 함께 실행합니다.

- Gazebo 테이블 3개 월드와 로봇
- Cartographer SLAM 및 `/map` 지도 생성
- Nav2 경로 계획·주행·복구 노드
- RViz 지도·로봇·경로 화면

저장된 지도가 없어도 Cartographer가 실행 중 지도를 만들고 Nav2가 이를 사용합니다.
`Managed nodes are active` 출력과 RViz의 지도·로봇 표시를 확인한 뒤 미션을 실행하세요.
`ros_dd_gazebo three_tables.launch.py`는 월드·로봇만 실행하므로 이 절차에서는 위 통합 런치를 사용합니다.

## 4. 하네스 Python 코드 시작 — 터미널 D

```bash
source /opt/ros/humble/setup.bash
source /home/robo/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=0
cd /home/robo/robot_harness
```

작업 위치는 `slam_harness_humble` 안이 아니라 **부모 폴더 `/home/robo/robot_harness`**입니다.
먼저 연결을 확인합니다.

```bash
ros2 service list | grep /slam_harness/fine_control
ros2 action list | grep /navigate_to_pose
```

### 자연어로 이동 실행

```bash
python3 -m slam_harness_humble.main '테이블 1번 들렀다가 3번으로 가' \
  --base-url http://127.0.0.1:8080/v1 \
  --model qwen3-8b \
  --ros-args -p use_sim_time:=true
```

검증된 계획을 출력한 뒤 실제 로봇 이동을 요청합니다.
한 명령에 한 미션을 실행하고 종료합니다. 다음 미션은 같은 터미널에서 새 명령으로 실행하세요.

계획만 확인하려면 `--dry-run`을 추가합니다.
이 옵션은 LLM을 호출하지만 ROS 노드를 생성하거나 로봇을 움직이지 않습니다.

```bash
python3 -m slam_harness_humble.main '테이블 1번 들렀다가 3번으로 가' \
  --base-url http://127.0.0.1:8080/v1 \
  --model qwen3-8b --dry-run
```

### 조건부 명령 예시

```bash
python3 -m slam_harness_humble.main \
  '테이블 1에 접근하는데 실패하면 3번까지 시도하고 다 실패하면 테이블 3으로 바로 갑니다' \
  --alignment skip --ros-args -p use_sim_time:=true

python3 -m slam_harness_humble.main \
  '로봇을 원점으로 이동시켜주세요' \
  --ros-args -p use_sim_time:=true

python3 -m slam_harness_humble.main \
  '테이블 1번에 3번 시도했는데 결국 실패하면 로봇 기준 뒤로 1미터 물러나서 처음부터 다시 시도 2번 해주세요' \
  --alignment skip --ros-args -p use_sim_time:=true
```

| 표현 | 실행 의미 |
| --- | --- |
| 3번까지 시도 | 최초 시도 포함 총 3회, 성공하면 남은 시도 생략 |
| 다 실패하면 테이블 3으로 | 모든 시도·라운드 실패 후 테이블 3에 1회 접근. 원래 목표 성공 시 생략 |
| 처음부터 다시 2번 | 최초 라운드 외에 추가 2라운드. 라운드당 3회라면 최대 접근 9회·후퇴 2회 |
| 뒤로 1m | 실패 당시 로봇이 바라보는 방향의 반대로 1m 후퇴 |
| 원점, 원정 | 현재 SLAM `map`의 `(x=0, y=0, yaw=0)` |

실패 조건은 Nav2 접근 이동에 적용합니다. 후퇴 실패·취소·미확인 제어 상태·연결 실패 시에는
후속 이동을 중단합니다. 과거 미션에서 시도한 횟수는 차감하지 않습니다.

기본값 `--alignment optional`은 접근 후 미세 정렬을 시도하되 일반적인 정렬 실패는 경고로 기록하고
다음 방문을 진행합니다. `--alignment skip`은 방문 후 미세 정렬을 생략합니다.
조건부 계획에 명시한 **라운드 사이 후퇴는 `skip`에서도 실행**됩니다.
정렬을 필수로 요구하려면 `--alignment required`를 사용합니다.

## 연결·동작 확인

| 증상 | 확인할 내용 |
| --- | --- |
| LLM 연결 실패 | 터미널 A의 모델 로딩, `/health`, `/v1/models` 확인 |
| `gate_unavailable` | 터미널 B 실행 여부와 `/slam_harness/fine_control`, 동일한 ROS 도메인 확인 |
| `move_to:unavailable` | 터미널 C의 Nav2 활성화와 `/navigate_to_pose` 확인 |
| `use_velocity_gate` 옵션을 인식하지 못함 | 실행 전 준비의 빌드 후 각 터미널에서 `install/setup.bash` 다시 적용 |
| RViz 목표로는 이동하지 않음 | 하네스 미션이 없을 때 아래 서비스로 Nav2 모드 선택 |

RViz 또는 `goto_pose.py`로 목표만 보내는 경우에는 게이트 제어권을 직접 전환합니다.

```bash
ros2 service call /slam_harness/fine_control \
  std_srvs/srv/SetBool "{data: false}"
```

Gazebo 화면에서 움직임이 불분명하다면 실제 모델 좌표와 속도를 확인합니다.

```bash
gz model -m ros_dd_robot -p
ros2 topic echo /cmd_vel
```

첫 명령의 앞 세 값은 Gazebo 모델의 `x y z`입니다. 미션 실행 중 다시 조회하여 비교하세요.
`/cmd_vel`에 이동 속도가 나오지 않으면 Nav2 입력과 게이트의 센서·제어권 상태를 확인합니다.

## 주요 코드와 설정

| 파일 | 역할 |
| --- | --- |
| `main.py` | CLI 옵션, 계획 출력, ROS 미션 시작·종료 |
| `llm_planner.py` | Qwen3 요청, `steps` 계획과 범위 검증 |
| `core.py` | 유한 재시도·후퇴·실패 분기·도착 콜백 |
| `ros_backend.py` | Nav2 Action, TF 위치 확인, 미세 제어 |
| `velocity_gate.py` | 속도 선택 서비스와 단일 `/cmd_vel` 출력 |
| `config/locations.yaml` | 테이블별 접근·정렬·후퇴 좌표 |

직접 지정한 `steps`의 시도 횟수는 그대로 사용합니다. 자연어에 횟수가 없으면
`--retries + 1`을 기본 총 시도 횟수로 사용하며, `--retries` 기본값은 1입니다.
기존 `{"waypoints":["table_1","table_3"]}` 직접 계획도 `--plan-json`으로 실행할 수 있습니다.
