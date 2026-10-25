# Three Tables: 지도를 먼저 만들고 하네스로 내비게이션하기

> 이 문서는 ros_dd 로봇용입니다. JDAMR Cube는 [jdamr_harness_readme.md](jdamr_harness_readme.md)를 사용합니다.

실행 순서는 다음과 같습니다.

```text
① Three Tables + Cartographer 실행
② 키보드로 로봇을 움직여 지도 관측
③ 지도 YAML·PGM 저장
④ 지도 작성 프로그램 종료
⑤ 방금 저장한 지도 + AMCL + Nav2 + 속도 게이트 실행
⑥ 초기 위치 및 테이블 접근 좌표 확인
⑦ 하네스로 자연어 명령을 받아 내비게이션
```

지도 작성과 운용은 **별도 단계**입니다.
지도 작성 중에는 하네스·Nav2·AMCL을 실행하지 않고,
하네스 운용 중에는 Cartographer를 실행하지 않습니다.

## 0. 한 번 빌드하고 터미널 환경 준비

ROS 2 Jazzy / Gazebo Harmonic과 필요한 시스템 패키지가 설치된 환경을 사용합니다.
처음 실행하거나 소스·설정을 변경했으면 빌드합니다. **지도가 없어도 빌드할 수 있습니다.**

```bash
source /opt/ros/jazzy/setup.bash
cd ~/robot_harness/harness_ws
colcon build --base-paths src
```

이후 **아래에서 여는 모든 ROS 터미널에 먼저** 적용합니다.

```bash
source ~/robot_harness/harness_ws/install/setup.bash
export ROS_DOMAIN_ID=0
```

다른 시뮬레이션이나 SLAM·내비게이션이 같은 ROS 도메인에 실행 중이라면
해당 터미널에서 `Ctrl+C`로 종료한 뒤 시작합니다.

## 1. 터미널 A — Three Tables 지도 작성 launch

```bash
ros2 launch ros_dd_navigation three_tables_mapping.launch.py
```

지도 작성 전용 launch이며 다음만 시작합니다.

- Gazebo 세 테이블 월드와 로봇, 센서·속도 브리지
- `three_tables.lua`를 사용하는 Cartographer와 `/map` 발행 노드
- 지도 작성용 RViz

**Nav2, AMCL, 속도 게이트, 하네스 미션은 시작하지 않습니다.**
Gazebo와 RViz에 로봇·LiDAR·지도가 나타나는지 확인하고 이 터미널을 유지합니다.
지도 작성 단계에서는 **2D Pose Estimate가 필요 없습니다.**

### Gazebo에서 탁자 번호 확인

탁자마다 색상이 다르고 상판과 양면 번호판에 흰색 숫자가 표시됩니다.

| 탁자 | 색상 | 기본 월드 기준 중심 좌표 (m) |
| --- | --- | --- |
| table_1 / 1번 | 빨강 | `(2.0, 1.5)` |
| table_2 / 2번 | 초록 | `(2.0, -1.5)` |
| table_3 / 3번 | 파랑 | `(-2.0, 1.5)` |

위 좌표는 Gazebo 월드 좌표이며 새로 만든 지도 좌표와는 별도로 확인합니다.
색상과 숫자는 시각 표시입니다. 탁자 위치·크기·충돌 형상과 LiDAR 높이의 장애물은 유지하므로
이 표시 변경 때문에 기존 지도를 다시 만들 필요는 없습니다.
월드 변경 후 `colcon build --packages-select ros_dd_gazebo`를 실행하고 Gazebo를 다시 시작합니다.

## 2. 터미널 B — 키보드로 지도 관측

```bash
ros2 run ros_dd_teleop asdw_teleop
```

이 터미널에 포커스를 두고 소문자 키를 입력합니다.

| 키 | 동작 |
| --- | --- |
| `w` / `s` | 전진 / 후진 |
| `a` / `d` | 좌회전 / 우회전 |
| Space / `k` | 정지 |

벽과 세 테이블 주변을 천천히 이동하며 관측합니다.
한 방향에서 가려지는 곳은 다른 방향에서도 관측하고,
RViz에서 벽·테이블 윤곽과 주행할 공간이 지도에 충분히 반영됐는지 확인합니다.
저장하기 전에 Space 또는 `k`로 로봇을 정지시킵니다.

## 3. 터미널 C — 만든 지도 저장

**터미널 A의 Gazebo와 Cartographer가 실행 중일 때** 저장합니다.

```bash
mkdir -p ~/robot_harness/harness_ws/maps/three_tables
ros2 run nav2_map_server map_saver_cli \
  -f ~/robot_harness/harness_ws/maps/three_tables/site_map \
  --ros-args -p use_sim_time:=true -p save_map_timeout:=10.0
```

이 문서에서는 기존 지도와 구분하기 위해 `site_map`이라는 이름을 사용합니다.
`-f`에는 `.yaml` 확장자를 붙이지 않습니다.
같은 이름의 파일이 이미 있으면 덮어쓰므로 보관할 지도와 다른 이름을 사용하세요.

저장 성공 메시지와 다음 두 파일을 확인합니다.

```bash
ls -lh ~/robot_harness/harness_ws/maps/three_tables/site_map.yaml \
       ~/robot_harness/harness_ws/maps/three_tables/site_map.pgm
```

```text
maps/three_tables/
├─ site_map.yaml   # 이미지 경로, 해상도, 원점 등
└─ site_map.pgm    # 실제 지도 이미지
```

두 파일을 함께 보관합니다. 지도 파일은 로봇의 현재 위치를 저장하는 파일이 아닙니다.

## 4. 지도 작성 단계 완전히 종료

1. 터미널 B에서 정지 후 `Ctrl+C`로 teleop을 종료합니다.
2. 터미널 A에서 `Ctrl+C`로 지도 작성 launch를 종료합니다.
3. Gazebo, Cartographer, 지도 작성용 RViz가 모두 종료될 때까지 기다립니다.

지도 저장 직후 Cartographer를 켜 둔 채 다음 단계를 시작하지 않습니다.
이후 Gazebo를 다시 실행하므로 로봇은 지도 작성 종료 위치가 아닌 기본 생성 위치에서 시작합니다.

## 5. 터미널 A — 방금 저장한 지도로 하네스 운용 launch

공통 환경을 적용하고 다음을 실행합니다.

```bash
ros2 launch slam_harness_jazzy three_tables_harness.launch.py \
  mode:=saved_map \
  map:=$HOME/robot_harness/harness_ws/maps/three_tables/site_map.yaml
```

이 명령은 **3단계에서 저장한 YAML 파일을 직접 읽습니다.**
지도 저장 후 다시 빌드하거나 지도를 설치 폴더로 복사할 필요가 없습니다.
다른 이름으로 저장했다면 `map` 인수도 그 파일명으로 바꿉니다.

운용 launch가 시작하는 구성은 다음과 같습니다.

| 구성 | 역할 |
| --- | --- |
| Three Tables Gazebo + 로봇·브리지 | 지도 작성 때와 같은 월드 및 기본 생성 위치 |
| map_server | 지정한 저장 지도를 읽어 `/map` 제공 |
| AMCL | 저장 지도와 센서로 로봇 위치 추정 |
| Nav2 | 경로 계획·추종·복구 |
| RViz | 초기 위치 입력과 지도·센서·경로 표시 |
| velocity_gate | Nav2 주행과 하네스 미세 제어의 속도 선택 |

**Cartographer와 지도 작성 노드는 시작하지 않습니다.**
`mode`의 기본값은 `saved_map`이고, 이 모드의 **`map` 인수는 필수**입니다.
지도를 생략하면 지도 작성부터 진행하라는 오류를 출력합니다.
기존 지도나 설치된 예전 지도 복사본을 자동으로 선택하지 않습니다.

## 6. RViz — 초기 위치와 테이블 좌표 확인

### AMCL 초기 위치 지정

새 지도를 처음 사용할 때는 수동으로 초기 위치를 확인합니다.

1. RViz의 **2D Pose Estimate**를 선택합니다.
2. 저장 지도에서 현재 Gazebo 로봇이 있는 위치를 누릅니다.
3. 로봇이 바라보는 방향으로 드래그한 뒤 놓습니다.
4. LiDAR 점이 지도에 그려진 벽·테이블 윤곽과 맞는지 확인합니다.
5. 터미널 A에서 `Nav2 ready: navigation goals can now be sent.`를 확인합니다.

초기 위치는 **방금 만든 지도 좌표계 기준**입니다.
새 지도의 초기 위치를 무조건 `(0,0,0)`이라고 가정하지 않습니다.
초기 위치를 지정하기 전에는 Nav2 활성화가 AMCL 위치 추정을 기다립니다.

### 하네스가 사용할 테이블 접근 좌표 확인

하네스는 테이블 좌표를 영상이나 지도에서 자동으로 찾아 등록하지 않습니다.
다음 파일에 등록된 접근·정렬·후퇴 좌표를 사용합니다.

```text
~/robot_harness/harness_ws/src/SLAM_harness_jazzy/config/locations.yaml
```

새 지도에서 등록 좌표가 각 테이블 바깥의 통행 가능한 위치와 일치하는지 확인합니다.
지도 원점·방향이 달라졌다면 이 좌표도 새 map 좌표계에 맞춰 수정합니다.
AMCL 초기 위치를 지정하는 작업과 테이블 좌표를 등록하는 작업은 별개입니다.

별도 좌표 파일을 사용하면 미션에 `--locations /절대경로/locations.yaml`을 지정합니다.
기본 좌표 파일을 수정했다면 `colcon build --packages-select slam_harness_jazzy`로
하네스를 다시 설치하고 미션 터미널에서 환경을 다시 불러옵니다.
**지도 파일만 새로 저장한 경우에는 재빌드가 필요 없습니다.**

## 7. 터미널 B — Qwen3 명령으로 내비게이션

공통 환경을 적용하고 기존 로컬 Qwen3 서버를 확인합니다.

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/v1/models
```

기본 서버는 `http://127.0.0.1:8080/v1`, 기본 모델은 `qwen3-8b`입니다.
서버가 다른 모델 이름을 요구하면 모델 목록의 ID를 `--model`로 지정합니다.

### 먼저 계획만 확인

```bash
ros2 run slam_harness_jazzy mission '테이블 1번 들렀다가 3번으로 가' --dry-run
```

LLM 계획을 검증하고 출력하며 로봇을 움직이지 않습니다.

### 등록된 접근 위치로 실제 내비게이션

터미널 A의 **Nav2 ready**와 6단계 좌표 확인을 마친 뒤 실행합니다.

```bash
ros2 run slam_harness_jazzy mission '테이블 1번 들렀다가 3번으로 가' \
  --alignment skip --ros-args -p use_sim_time:=true
```

먼저 `--alignment skip`으로 Nav2 접근 위치까지의 방문을 확인합니다.
미세 정렬까지 수행하려면 좌표를 확인한 뒤 다음과 같이 실행합니다.

```bash
ros2 run slam_harness_jazzy mission '테이블 1번 들렀다가 3번으로 가' \
  --alignment required --ros-args -p use_sim_time:=true
```

`required`는 정렬 실패 시 등록된 후퇴 위치로 후퇴하고 미션을 중단합니다.
기본값 `optional`은 일반적인 정렬 실패를 경고로 기록하고 다음 방문을 진행합니다.
한 번에 한 미션만 실행하며 미션 중 teleop이나 다른 목표 입력 노드를 함께 실행하지 않습니다.
종료 시 성공 여부와 방문 결과를 JSON으로 출력합니다.

### 로봇이 탁자에서 떨어져 멈추는 이유

현재 기본 좌표는 탁자에 접촉하지 않고 앞에서 정지하도록 설정되어 있습니다.
세 탁자 모두 접근점과 정렬점이 탁자 바깥에 등록되어 있습니다.

| 실행 정책 | 정지 목표 | 로봇 기준점에서 탁자 가장자리까지의 설계 거리 |
| --- | --- | --- |
| `--alignment skip` | Nav2 접근점 `approach` | 약 1.15m |
| `--alignment required` | 접근 후 정렬점 `align` | 정렬 성공 시 약 0.55m |
| 옵션 생략 (`optional`) | 정렬 시도 | 실패하면 접근점 부근에 남고 경고로 완료될 수 있음 |

거리는 기본 월드·좌표가 일치할 때 `base_footprint` 기준으로 계산한 값입니다.
차체 끝과의 간격은 이보다 작으며, Nav2 위치 허용 오차와 위치 추정 오차에 따라 실제 위치가 달라집니다.
현재 Nav2 일반 도착 위치 허용 오차는 0.25m입니다.
`required`도 탁자에 닿는 동작을 의미하지 않습니다.
정렬이 실패하면 결과의 `reason` 또는 `warnings`에서 `align_to` 오류를 확인합니다.

## 8. 종료와 다음 운용

1. 미션 완료를 기다리거나 터미널 B에서 `Ctrl+C`로 중단합니다.
2. 터미널 A에서 `Ctrl+C`로 운용 launch를 종료합니다.
3. 다음 운용 때는 지도를 다시 만들지 않고 **5단계부터** 같은 YAML을 지정해 실행합니다.
4. 환경이 바뀌어 새 지도가 필요할 때만 **1단계부터** 다시 진행합니다.

## 선택 사항 — 확인된 초기 위치 자동 전달

같은 지도와 같은 생성 위치에서 초기 위치를 확인·기록한 뒤에만 사용합니다.
아래 `0.0`은 입력 형식 예시이며, 새 지도에서 확인한 값으로 바꿔야 합니다.
`initial_yaw` 단위는 라디안입니다.

```bash
ros2 launch slam_harness_jazzy three_tables_harness.launch.py \
  map:=$HOME/robot_harness/harness_ws/maps/three_tables/site_map.yaml \
  set_initial_pose:=true initial_x:=0.0 initial_y:=0.0 initial_yaw:=0.0
```

이 경우 RViz 초기 위치 입력을 생략할 수 있습니다.
`gui:=false use_rviz:=false`를 추가하면 화면 없이 실행합니다.
지도·월드·로봇 시작 위치가 바뀌면 초기 위치를 다시 확인합니다.

## 문제가 있을 때

| 증상 | 확인 |
| --- | --- |
| 지도 작성 launch가 기존 노드 충돌로 종료 | 이전 지도 작성·운용 launch를 완전히 종료 |
| 지도 저장 실패 | 지도 작성이 실행 중인지, `/map`이 발행되는지 확인 |
| `map` 인수 누락 오류 | 3단계에서 저장한 YAML을 `map:=...`로 지정 |
| 지도 또는 이미지 파일 없음 | YAML과 참조하는 PGM이 모두 있는지 확인 |
| AMCL 위치 대기 / `navigation_not_ready` | 2D Pose Estimate, LiDAR 정렬, Nav2 ready 로그 확인 |
| 다른 테이블이나 장애물로 이동 | 새 지도 기준으로 `locations.yaml` 재확인 |
| `gate_unavailable` | 운용 launch, `/slam_harness/fine_control` 서비스, ROS 도메인 확인 |

`ros_dd.launch.py` 기본 월드의 지도 작성 방법은 [readme.md](readme.md)에 있습니다.
이 문서의 지도·좌표는 **Three Tables 월드**용입니다.
