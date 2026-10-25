# ros_dd와 JDAMR Cube SLAM 비교 및 이식 기준

## 기준 소스

원본 `bimanual-robot/src/navigation`을 읽고 다음 현재 실행 경로를 기준으로 선택했습니다.
원본 파일은 수정하지 않았으며, 변경 없이 가져온 파일의 SHA-256은
[IMPORT_PROVENANCE.json](IMPORT_PROVENANCE.json)에 기록했습니다.

- `jdamr_cube_bringup/launch/real_bringup.launch.py`: **new_base_real.urdf**와 바퀴 반경 0.0329m, 중심 간격 0.510m
- `jdamr_cube_navigation/launch/operator_mapping.launch.py` → `cartographer_real.launch.py` → **jdamr_cube_2d_real.lua**
- `jdamr_cube_navigation/config/new_base_nav2_params.yaml`: 현재 실차 footprint, AMCL, MPPI/RPP, Collision Monitor
- `behavior_trees/navigate_to_pose_staging_navfn_mppi.xml`: 원본이 제공하는 NavFn + MPPI staging 변형

`jdamr_cube.urdf`의 예전 시뮬레이터 모델은 바퀴 반경 0.075m·간격 0.35m이고 팔이 포함됩니다.
현재 실차 bringup의 로봇과 다르므로 이를 실제 로봇 제원으로 간주해 복사하지 않았습니다.
이번 모델의 범위는 원본 `new_base_geometry.yaml`이 명시한 **현재 하단 베이스, 양팔·하중 제외**입니다.

## SLAM 방식은 같은 계열이며 파라미터와 센서 계약이 다름

| 항목 | 기존 ros_dd three-table | 이번 JDAMR 기준 |
| --- | --- | --- |
| 지도 작성 | Cartographer 2D | Cartographer 2D 실차 프로파일 |
| tracking_frame | base_footprint | base_link |
| published_frame / odom_frame | odom / odom | odom / odom |
| map→odom 담당 | Cartographer | Cartographer |
| odom→base 담당 | Gazebo DiffDrive | 실차 드라이버 대신 JDAMR Gazebo DiffDrive |
| 바퀴 odometry 사용 | true | **true: 실차 real/corridor 기준 유지** |
| Cartographer IMU 사용 | false | false: 원본 실차도 미사용 |
| SLAM min/max range | 0.1 / 8.0m | real 기반: 0.12 / 8.0m (시뮬레이션 기본값) |
| missing_data_ray_length | 3.0m | real: 1.0m |
| pose_publish_period_sec | 0.005s | 0.05s |
| 저장 지도 운용 | map_server + AMCL | map_server + AMCL |
| 로컬 제어 | DWB | 가져온 실차 설정의 MPPI와 RPP, 기본 BT는 NavFn+MPPI |
| 충돌 판단 | 하네스 원형 게이트 | 실차 비대칭 footprint 및 Collision Monitor의 원본 polygons |

**SLAM 알고리즘 자체가 ros_dd는 Cartographer, JDAMR는 다른 알고리즘인 것은 아닙니다.**
차이는 프레임·거리·가중치·TF 주기·차체 제원 및 제어 경로입니다.

원본의 예전 Gazebo 프로파일 `jdamr_cube_2d.lua`는 초기 odometry 타임스탬프 문제 회피를 위해
`use_odometry=false`입니다. 이를 실차 기준으로 오인하지 않고, 기본 지도 작성은
`jdamr_cube_2d_real.lua`를 그대로 사용합니다. 이 구성으로 모의 odometry+scan 입력을 검증합니다.

`corridor.lua`도 선택 가능하도록 원본 그대로 보관했습니다.
해당 파일은 주석 일부가 상관매칭 ON이라고 설명하지만 실제 실행값은
`use_online_correlative_scan_matching=false`입니다. 이 차이를 임의로 고치거나
real 프로파일과 섞지 않았습니다. 기본 real 프로파일의 실제 값은 true입니다.

원본 `ekf_odom_imu.launch.py`는 그 파일 설명상 현재 bringup에 포함되지 않는 선택 경로입니다.
따라서 기존 실차 기준을 지키기 위해 이번 기본 시뮬레이션에 EKF를 새로 끼워 넣지 않았습니다.
`jdamr_cube_vslam`의 RGB-D/RTAB-Map도 별도 경로이며 기본 2D 운용과 구분합니다.

## 시뮬레이터에 맞춘 변경만 어댑터로 분리

가져온 실차 URDF와 Nav2 YAML, Cartographer LUA는 원본 사본으로 남겨 비교할 수 있습니다.

- `new_base_sim.urdf`: 원본 고정 TF·바퀴 치수·기존 rail 충돌 형상 유지
- Gazebo용 관성·접촉·DiffDrive·JointStatePublisher 및 10Hz GPU LiDAR 추가
- G4 모델: 원본 장착 `(-0.010,0,0.150)`, yaw=π 및 측정 범위 0.28~16m 반영
- 모의 LaserScan은 Gazebo의 정상적인 각도 순서를 사용하며 실차 시리얼 패킷을 재현하지 않음
- 시뮬레이션 관성과 캐스터 구 형상은 동역학 실행을 위한 모델링 값이며 실측 질량·마찰 보정값이 아님
- 모든 실행 노드의 use_sim_time=true; 실차 시계·UART·USB 드라이버는 사용하지 않음
- 하네스 mux를 Collision Monitor **앞**에 삽입해 Nav2 및 미세 제어 모두 동일한 원본 충돌 검사를 거침
- NavFn/MPPI staging 트리에 필요한 position checker ID를 원본 PositionGoalChecker 설정으로 연결
- 선택한 원본 BT가 사용하지 않는 Lattice planner와 실차 전용 Keepout 운영 파일·서비스는 시작하지 않음
- 원본의 비활성 keepout 설정은 보관하되 이 예제는 Keepout mask를 운영하지 않음
- AMCL 초기 위치를 수동 지정하거나 검증된 좌표로 명시 전달하고, 최신 map TF 후 Nav2 활성화
- JDAMR staging은 위치만 판정하므로 뒤따르는 저속 방향 정렬을 위해 JDAMR wrapper의 align-timeout 기본값을 60초로 설정 (사용자 지정값 유지)

원본 YAML에 있는 숫자·polygon을 ros_dd 파라미터로 덮어쓰지 않았습니다.
실행 시계·파일 경로·입출력 토픽·필수 checker 연결은 `jdamr_cube_harness/parameters.py`에서
명시적으로 적용합니다. MPPI 수치, footprint, StopZone polygon은 가져온 설정을 유지합니다.

## 재사용과 독립성

Qwen3 JSON 계획·계획 검증·재시도·후퇴·미세 제어 엔진은 `SLAM_harness_jazzy`를 재사용합니다.
`jdamr_cube_harness mission`은 별도 JDAMR `locations.yaml`을 선택합니다.
탁자 월드와 숫자 표시는 기존 three-table 자산을 이식했지만 로봇은 JDAMR 모델입니다.
실행 시 `bimanual-robot`이나 `ros2_ws`를 source하지 않으며, 실차·원본 워크스페이스를 수정하지 않습니다.

시뮬레이터 주행 성공을 실제 로봇의 센서 잡음·슬립·하중 변화·정밀 주차 검증으로 해석하지 않습니다.
실제 수행한 검증은 [VALIDATION.md](VALIDATION.md)에 기록합니다.

## 시뮬레이션 관측 거리 조정

실차 원본 프로파일의 `max_range=3.5`는 사본에 그대로 보존합니다.
지도 작성 launch는 선택한 real/corridor 설정에서 실행용 Lua를 생성하고
`max_range`만 기본 8m로 덮어씁니다. `slam_max_range`로 0.28m 초과~16m 이하를
선택할 수 있습니다. 모의 G4 센서의 측정 범위 0.28~16m, odometry, TF,
IMU 사용 여부와 `missing_data_ray_length` 등 나머지 설정은 유지합니다.
실행용 파일은 launch 종료 시 제거합니다. 저장 지도를 사용하는 AMCL/Nav2에는
이 Cartographer 거리 인자가 적용되지 않습니다.
