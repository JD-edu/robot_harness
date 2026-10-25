# JDAMR Cube: Three Tables 지도 작성 → 저장 → 하네스 내비게이션

이 문서는 `jdamr_cube_harness`용입니다. 기존 `ros_dd` 실행 방법은
[harness_readme.md](harness_readme.md)에 있습니다. 두 로봇을 같은 ROS 도메인에 동시에 실행하지 않습니다.

JDAMR 원본의 현재 `real_bringup.launch.py`가 사용하는 `new_base_real.urdf`를 기준으로
Gazebo 모델을 구성했습니다. 예전 Gazebo용 `jdamr_cube.urdf`의 큰 바퀴 모델과 다릅니다.
지도 작성에는 **JDAMR 실차용 Cartographer 프로파일**, 운용에는 **AMCL + NavFn/MPPI + Collision Monitor**를 사용합니다.
[SLAM 비교와 이식 범위](jdamr_cube_simulation/SLAM_COMPARISON.md)를 참고하세요.

## 0. 빌드와 공통 환경

시스템 ROS 2 Jazzy와 Gazebo Harmonic이 설치된 새 터미널에서 빌드합니다.

```bash
source /opt/ros/jazzy/setup.bash
cd ~/robot_harness/harness_ws
colcon build --base-paths src
```

이후 사용하는 **각 ROS 터미널**에서 적용합니다.

```bash
source ~/robot_harness/harness_ws/install/setup.bash
export ROS_DOMAIN_ID=0
```

별도의 `bimanual-robot` 또는 `ros2_ws`를 source할 필요가 없습니다.
원본 소스는 수정하지 않았고 필요한 파일은 `harness_ws/src/jdamr_cube_simulation`에 가져왔습니다.
기존 Gazebo·SLAM·Nav2·teleop·하네스 미션을 종료한 뒤 시작합니다.

## 1. 터미널 A — JDAMR로 지도 만들기

```bash
ros2 launch jdamr_cube_harness three_tables_mapping.launch.py
```

이 launch가 시작하는 구성:

- 빨강 1번·초록 2번·파랑 3번 탁자가 있는 Gazebo 월드
- JDAMR 현재 실차 모델에서 파생한 차동구동 로봇, G4 장착 위치의 모의 LiDAR, odometry·TF 브리지
- 실차 `jdamr_cube_2d_real.lua`를 기반으로 관측 거리를 8m로 확장한 시뮬레이션용 Cartographer
- 지도 작성용 RViz

Nav2·AMCL·하네스 미션·Collision Monitor는 아직 실행하지 않습니다.
**2D Pose Estimate는 필요 없습니다.**

화면 없이 실행하려면 `gui:=false use_rviz:=false`를 추가합니다.
원본 복도용 설정이 필요하면 `slam_profile:=corridor`로 선택할 수 있습니다.
선택한 프로파일에 시뮬레이션용 거리 설정만 적용하며 실차 원본 파일은 수정하지 않습니다.

모의 라이다 측정 범위는 0.28~16m이고, SLAM은 기본적으로 8m까지 사용합니다.
더 멀리 관측하려면 다음처럼 설정합니다(최대 16m).

```bash
ros2 launch jdamr_cube_harness three_tables_mapping.launch.py slam_max_range:=12.0
```

기존 실차 프로파일의 거리 제한을 재현하려면 `slam_max_range:=3.5`를 사용합니다.
거리 변경은 지도 작성 launch를 종료하고 다시 시작해야 적용됩니다.

## 2. 터미널 B — 수동으로 주변 관측

```bash
ros2 run jdamr_cube_harness teleop
```

| 키 | 동작 |
| --- | --- |
| `w` / `s` | 전진 0.12m/s / 후진 0.08m/s |
| `a` / `d` | 좌회전 / 우회전 0.3rad/s |
| Space | 정지 |
| Ctrl+C | 정지 후 종료 |

키를 누르고 있는 동안 이동하며, 키 입력이 0.3초 없으면 정지합니다.
**JDAMR 시뮬레이션의 기본 SLAM 관측 범위는 8m**입니다.
원점에서 회전만 하지 말고 방의 벽과 세 탁자 주변을 이동하며 관측합니다.
RViz에서 지도 윤곽과 주행할 공간이 충분히 관측됐는지 확인하고 정지합니다.

## 3. 터미널 C — JDAMR 지도 저장

지도 작성 launch가 실행 중이고 로봇이 정지한 상태에서 저장합니다.

```bash
mkdir -p ~/robot_harness/harness_ws/maps/jdamr_three_tables
ros2 run nav2_map_server map_saver_cli \
  -f ~/robot_harness/harness_ws/maps/jdamr_three_tables/site_map \
  --ros-args -p use_sim_time:=true -p save_map_timeout:=10.0
```

`site_map.yaml`과 `site_map.pgm`이 생성됩니다. 두 파일을 함께 보관합니다.
같은 이름의 기존 파일은 덮어쓰므로 보관할 지도와 다른 이름을 사용합니다.
`ros_dd` 지도와 구분해 JDAMR가 직접 관측한 지도를 사용합니다.

## 4. 지도 작성 종료

1. 터미널 B에서 Space 후 Ctrl+C로 teleop 종료
2. 터미널 A에서 Ctrl+C로 Gazebo·Cartographer·RViz 종료
3. 모두 종료된 뒤 저장 지도 운용 시작

지도 작성과 저장 지도 운용을 동시에 시작하지 않습니다.
재시작한 로봇은 지도 작성 종료 위치가 아니라 기본 생성 위치에서 시작합니다.

## 5. 터미널 A — 저장 지도 기반 JDAMR 하네스 운용

```bash
ros2 launch jdamr_cube_harness three_tables_harness.launch.py \
  map:=$HOME/robot_harness/harness_ws/maps/jdamr_three_tables/site_map.yaml
```

`map`은 필수입니다. 저장한 YAML을 직접 읽으므로 지도 저장 후 재빌드할 필요가 없습니다.
Gazebo JDAMR, map_server, AMCL, Nav2, Collision Monitor, 속도 중재기와 RViz가 함께 시작됩니다.
**Cartographer는 시작하지 않습니다.**

RViz에서 다음을 수행합니다.

1. **2D Pose Estimate**로 저장 지도상의 실제 로봇 위치·방향 지정
2. LiDAR와 지도의 벽·탁자 윤곽이 맞는지 확인
3. `Nav2 ready: navigation goals can now be sent.` 로그 확인

지도 원점과 Gazebo 월드 원점이 같다고 가정하지 않습니다.
검증된 초기 좌표가 있다면 자동 전달할 수 있습니다.
다음 `0.0`은 형식 예시이므로 해당 지도에서 확인한 값으로 바꿉니다. yaw는 라디안입니다.

```bash
ros2 launch jdamr_cube_harness three_tables_harness.launch.py \
  map:=$HOME/robot_harness/harness_ws/maps/jdamr_three_tables/site_map.yaml \
  set_initial_pose:=true initial_x:=0.0 initial_y:=0.0 initial_yaw:=0.0
```

`gui:=false use_rviz:=false`를 추가하면 화면 없이 실행합니다.
수동 초기화 모드에서 RViz를 끈 경우에는 별도 노드로 `/initialpose`를 전달해야 합니다.

## 6. 새 지도에서 탁자 접근 좌표 확인

JDAMR 미션이 기본으로 읽는 별도 좌표 파일:

```text
harness_ws/src/jdamr_cube_simulation/jdamr_cube_harness/config/locations.yaml
```

세 탁자의 접근·정렬·후퇴 위치를 **새 JDAMR 지도 좌표계**에서 확인합니다.
로봇은 탁자 위치를 영상이나 지도에서 자동 등록하지 않습니다.
다른 파일을 쓰려면 미션에 `--locations /절대경로/locations.yaml`을 지정합니다.
기본 파일을 수정했다면 `colcon build --packages-select jdamr_cube_harness` 후 환경을 다시 적용합니다.

기본 좌표 예시는 접근점에서 로봇 기준점과 탁자 가장자리 간 거리가 약 1.15m,
정렬점에서 약 0.55m입니다. JDAMR의 기준점과 비대칭 차체 외곽은 ros_dd와 다릅니다.
이것은 탁자 접촉·정밀 주차 기능이 아니라 정해진 map 좌표로의 방문·정렬입니다.

## 7. 터미널 B — 로컬 Qwen3 명령으로 내비게이션

기존 서버를 사용합니다. 기본 주소는 `http://127.0.0.1:8080/v1`, 모델은 `qwen3-8b`입니다.
다른 서버·모델은 `--base-url`, `--model`로 지정합니다.

```bash
# 계획만 확인, 이동 없음
ros2 run jdamr_cube_harness mission '테이블 1번, 2번, 3번 순서로 방문해' --dry-run

# Nav2 접근 위치까지 실제 방문
ros2 run jdamr_cube_harness mission '테이블 1번, 2번, 3번 순서로 방문해' \
  --alignment skip --ros-args -p use_sim_time:=true

# 접근 후 미세 정렬까지 필수로 수행
ros2 run jdamr_cube_harness mission '테이블 1로 가' \
  --alignment required --ros-args -p use_sim_time:=true
```

LLM 계획 검증·유한 재시도·후퇴·실패 분기는 기존 하네스 엔진을 재사용합니다.
`jdamr_cube_harness mission`은 JDAMR 좌표 파일을 기본으로 선택합니다.
옵션 생략 시 `optional` 정렬을 사용하며 일반적인 정렬 실패는 경고로 처리합니다.
JDAMR의 원본 staging은 위치만 판정하므로 저속 방향 정렬까지 고려해
미세 정렬 제한시간 기본값을 60초로 둡니다. `--align-timeout`으로 바꿀 수 있습니다.

한 번에 한 미션만 실행합니다. 운용 중 teleop을 동시에 실행하지 않습니다.
속도 경로는 다음과 같습니다.

```text
Nav2 MPPI/RPP → velocity_smoother → /slam_harness/nav_cmd_vel ┐
하네스 미세 제어 → /slam_harness/fine_cmd_vel                ├→ JDAMR mux
JDAMR mux → /jdamr_harness/selected_cmd_vel → Collision Monitor → /cmd_vel → Gazebo
```

미세 정렬·후퇴 명령도 원본 JDAMR의 StopZone·FootprintApproach 검사를 거칩니다.
ros_dd의 원형 속도 게이트는 이 로봇에서 시작하지 않습니다.

## 8. 종료와 확인

미션 완료를 기다리거나 터미널 B에서 Ctrl+C로 중단한 뒤,
터미널 A에서 Ctrl+C로 전체 운용 launch를 종료합니다.

```bash
ros2 lifecycle get /amcl
ros2 lifecycle get /collision_monitor
ros2 lifecycle get /bt_navigator
ros2 topic info /cmd_vel -v
```

운용 중 `/cmd_vel` 발행자는 Collision Monitor 하나여야 합니다.
초기 위치 설정 후 세 lifecycle 노드가 active인지 확인합니다.
다음 운용은 같은 지도 경로로 **5단계부터** 시작합니다.

이 구현은 Gazebo용입니다. 실차 UART·USB 드라이버나 systemd 서비스는 실행하지 않습니다.
상부 양팔·하중·RGB-D 카메라 및 RTAB-Map 경로는 이번 AMR 2D SLAM 이식 범위에 포함하지 않습니다.
