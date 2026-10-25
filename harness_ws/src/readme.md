# ROS 2 Jazzy · ros_dd 지도 작성과 주행

ROS 2 Jazzy / Gazebo Harmonic에서 **`ros_dd_gazebo/ros_dd.launch.py`의 기본 월드**를
사용하는 실행 안내입니다. 필요한 소스는 `~/robot_harness/harness_ws`에 포함되어 있습니다.

| 방법 | 지도 공급 | 위치 추정 | 지도 저장 | 초기 위치 수동 입력 |
| --- | --- | --- | --- | --- |
| 1. 지도 만들기 | Cartographer가 생성 | Cartographer | 작성 후 저장 | 필요 없음 |
| 2. 저장 지도로 주행하기 | 저장한 YAML·PGM | AMCL | 기존 지도 사용 | 필요 |
| 3. 지도 저장 없이 SLAM과 주행 동시에 하기 | Cartographer가 실시간 생성 | Cartographer | 필요 없음 | 필요 없음 |

2번은 저장 지도에서의 위치 추정과 내비게이션입니다.
3번은 온라인 SLAM 내비게이션으로, 실행할 때마다 새 지도를 만듭니다.

## 공통 준비

시스템 ROS 2 Jazzy, Gazebo Harmonic, Cartographer, Nav2가 설치된 환경을 사용합니다.
처음 실행하거나 소스·설정을 변경했다면 새 터미널에서 빌드합니다.

```bash
source /opt/ros/jazzy/setup.bash
cd ~/robot_harness/harness_ws
colcon build --base-paths src --packages-up-to ros_dd_simulation
```

이후 사용하는 **모든 터미널에서** 다음을 먼저 실행합니다.

```bash
source ~/robot_harness/harness_ws/install/setup.bash
export ROS_DOMAIN_ID=0
```

아래 1·2·3번은 각각 독립적인 실행 방법입니다.
다른 방법으로 전환할 때는 기존 teleop, Gazebo, Cartographer, Nav2, RViz를
해당 터미널에서 `Ctrl+C`로 종료하고 종료가 완료된 뒤 시작합니다.
각 프로그램은 하나씩만 실행합니다.

`ros_dd.launch.py`는 기본적으로 `ros_dd.world`에 로봇을
`x=0`, `y=0.5`, `yaw=0`으로 생성하고 센서·속도 브리지를 실행합니다.
Cartographer와 Nav2는 아래 절차에 따라 별도 터미널에서 시작합니다.

## 1. 지도 만들기

Gazebo와 Cartographer를 켜고, 키보드로 로봇을 움직여 지도를 만든 뒤 파일로 저장합니다.
이 단계에서는 Nav2와 AMCL을 실행하지 않습니다.

### 터미널 A — 시뮬레이션 실행

```bash
ros2 launch ros_dd_gazebo ros_dd.launch.py
```

Gazebo 기본 월드와 로봇이 생성되는지 확인합니다.

### 터미널 B — Cartographer와 RViz 실행

```bash
ros2 launch ros_dd_cartographer ros_dd_cartograph.launch.py use_sim_time:=true
```

기본 설정 `ros_dd_cartographer.lua`를 사용합니다.
RViz에 `/map`과 로봇, LiDAR가 표시되는지 확인합니다.

### 터미널 C — 로봇을 움직여 주변 관측

```bash
ros2 run ros_dd_teleop asdw_teleop
```

키보드 입력은 이 터미널에 포커스를 둔 상태에서 소문자로 입력합니다.

| 키 | 동작 |
| --- | --- |
| `w` | 전진 |
| `s` | 후진 |
| `a` / `d` | 좌회전 / 우회전 |
| Space / `k` | 정지 |

월드의 벽과 장애물 주변을 충분히 관측합니다.
한 방향에서 가려진 부분은 다른 방향에서 관측해 지도에 반영합니다.
RViz에서 지도 윤곽을 확인한 뒤 로봇을 정지시킵니다.

### 터미널 D — 지도 저장

**터미널 A·B가 실행 중이고 로봇이 정지한 상태에서** 저장합니다.
다음 경로에 파일이 이미 있으면 덮어쓰므로, 기존 지도를 보관하려면 `map` 대신 다른 이름을 사용합니다.

```bash
mkdir -p ~/robot_harness/harness_ws/maps/ros_dd
ros2 run nav2_map_server map_saver_cli \
  -f ~/robot_harness/harness_ws/maps/ros_dd/map \
  --ros-args -p use_sim_time:=true -p save_map_timeout:=10.0
```

`-f`에는 확장자를 붙이지 않습니다. 저장 성공 후 다음 두 파일이 생성됩니다.

```text
~/robot_harness/harness_ws/maps/ros_dd/
├─ map.yaml   # 이미지 경로, 해상도, 지도 원점 등
└─ map.pgm    # 실제 격자 지도 이미지
```

두 파일을 함께 보관합니다. 지도 저장은 로봇의 현재 위치를 저장하는 동작과 다릅니다.

### 지도 작성 종료

1. 터미널 C에서 정지 후 `Ctrl+C`로 teleop을 종료합니다.
2. 터미널 B에서 `Ctrl+C`로 Cartographer와 RViz를 종료합니다.
3. 터미널 A에서 `Ctrl+C`로 Gazebo와 로봇 관련 노드를 종료합니다.

## 2. 저장 지도로 주행하기

1번에서 저장한 지도 또는 같은 기본 월드에서 작성한 지도를 사용합니다.
Cartographer는 실행하지 않고, map_server가 지도를 읽으며 AMCL이 현재 위치를 추정합니다.

### 터미널 A — 시뮬레이션 실행

```bash
ros2 launch ros_dd_gazebo ros_dd.launch.py
```

Gazebo를 새로 시작하면 로봇도 기본 생성 위치에서 시작합니다.
지도 작성 종료 시점의 위치에서 이어서 시작하는 것은 아닙니다.

### 터미널 B — 저장 지도와 내비게이션 실행

```bash
ros2 launch ros_dd_navigation navigation.launch.py \
  use_localization:=true \
  use_sim_time:=true \
  map:=$HOME/robot_harness/harness_ws/maps/ros_dd/map.yaml
```

map_server, AMCL, Nav2, 내비게이션용 RViz가 실행됩니다.
기본 Nav2 설정 `nav2_params.yaml`을 사용합니다.
`map`에는 1번에서 실제로 저장한 지도의 YAML 경로를 지정합니다.

### RViz — 초기 위치 지정

1. **2D Pose Estimate**를 선택합니다.
2. 저장 지도에서 로봇의 실제 위치를 누릅니다.
3. 로봇이 바라보는 방향으로 드래그한 뒤 놓습니다.
4. LiDAR 점들이 지도의 벽·장애물 윤곽과 맞는지 확인합니다.
5. 터미널 B에 `Nav2 ready: navigation goals can now be sent.`가 출력될 때까지 기다립니다.

초기 위치는 **저장 지도 좌표계 기준**입니다.
Gazebo의 로봇 생성 좌표 `(0, 0.5)`를 그대로 지도상의 초기 위치라고 가정하지 않습니다.
초기 위치가 지정되지 않으면 Nav2 활성화가 위치 추정을 기다립니다.

### RViz — 목표 주행

**2D Goal Pose**를 선택하고 이동할 위치를 누른 뒤 도착 방향으로 드래그합니다.
목표는 로봇이 접근할 수 있는 빈 공간으로 지정합니다.
경로와 코스트맵을 보려면 RViz의 **Global Planner**, **Local Planner** 표시를 켭니다.

저장 지도는 주행 중 새로 작성하거나 갱신하지 않습니다.
종료할 때는 터미널 B의 내비게이션을 먼저 종료하고 터미널 A의 시뮬레이션을 종료합니다.

## 3. 지도 저장 없이 SLAM과 주행 동시에 하기

저장 지도 없이 Cartographer가 실시간으로 만드는 지도를 Nav2가 사용합니다.
Gazebo → Cartographer → Nav2 순서로 실행하고, 세 터미널을 모두 유지합니다.

### 터미널 A — 시뮬레이션 실행

```bash
ros2 launch ros_dd_gazebo ros_dd.launch.py
```

### 터미널 B — Cartographer 실행

```bash
ros2 launch ros_dd_cartographer ros_dd_cartograph.launch.py \
  use_sim_time:=true use_rviz:=false
```

기본 `ros_dd_cartographer.lua`로 지도를 만듭니다.
RViz는 다음 터미널에서 내비게이션용으로 실행하므로 여기서는 끕니다.

### 터미널 C — 실시간 지도에 Nav2 연결

```bash
ros2 launch ros_dd_navigation navigation.launch.py \
  use_localization:=false use_sim_time:=true
```

기본 Nav2 설정 `nav2_params.yaml`을 사용합니다.
`use_localization:=false`이므로 map_server와 AMCL을 실행하지 않습니다.
Cartographer가 `/map`과 지도 기준 위치 추정 TF를 제공하고, Nav2와 RViz가 이를 사용합니다.
저장 지도 경로 `map`을 지정할 필요가 없습니다.
`Managed nodes are active` 로그와 RViz의 지도·로봇 표시를 확인합니다.

### RViz — 초기 위치 입력 없이 목표 주행

**2D Pose Estimate는 필요 없습니다.**
**2D Goal Pose**로 현재 지도에서 통행 가능한 위치와 도착 방향을 지정합니다.
이동하면서 센서로 관측한 영역이 지도에 추가됩니다.
아직 관측하지 않은 먼 영역보다 현재 확인된 빈 공간부터 목표를 지정합니다.

이 방법에서는 지도 저장 명령을 실행할 필요가 없습니다.
종료한 뒤 다시 실행하면 기존 지도에서 이어지는 것이 아니라 새 지도를 만듭니다.

종료할 때는 터미널 C의 Nav2, 터미널 B의 Cartographer,
터미널 A의 Gazebo 순서로 `Ctrl+C`를 눌러 종료합니다.

## 선택 사항 — 터미널에서 목표 좌표 입력

2번 또는 3번에서 Nav2가 활성화된 뒤, RViz 대신 별도 터미널에서 실행할 수 있습니다.
2번의 AMCL 초기 위치 지정은 먼저 완료해야 합니다.

```bash
ros2 run ros_dd_nav2 goto_pose --ros-args -p use_sim_time:=true
```

입력 형식은 `x y` 또는 `x y yaw`이며, 위치는 map 좌표계의 미터, yaw는 도 단위입니다.

```text
1.0 0.0
0.5 -0.5 90
cancel
q
```

위 좌표는 입력 형식 예시입니다. 실제 목표는 현재 지도의 빈 공간에서 선택합니다.
`cancel`은 이동 취소, `q`는 입력 노드 종료입니다.
자동 주행 중에는 teleop을 함께 실행하지 않습니다.
