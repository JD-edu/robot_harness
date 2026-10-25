# JDAMR Cube 실차·Gazebo 설정 비교

현재 Gazebo 구성은 실차의 로봇 모델과 Cartographer·Nav2 설정을 기반으로 하며, 하드웨어 입출력을 Gazebo로 대체합니다. 실차 원본 파일은 보존하고 실행 시 필요한 설정만 별도로 적용합니다.

기준: 2026-10-22 현재 코드. 실차 기준 소스는 `bimanual-robot/src/navigation`이며, 이식한 소스는 `harness_ws/src/jdamr_cube_simulation`에 있습니다.

## 설정 차이표

| 항목 | 실차 기준 | 현재 Gazebo |
| --- | --- | --- |
| 로봇 모델 | 현재 bringup의 `new_base_real.urdf` | 해당 모델에서 파생한 `new_base_sim.urdf` |
| 바퀴 반경·중심 간격 | 0.0329m / 0.510m | 동일 |
| 라이다 측정 범위 | 0.28~16m | 동일 |
| 라이다 장착 위치·방향 | laser_link, 위치 (-0.010, 0, 0.150)m, yaw=π | 동일 |
| 라이다 측정점 수 | 실측 기록에서 스캔당 905~953개로 변동 | 스캔당 720개 고정 |
| 라이다 각도 순서 | 실측 기록에서 음의 방향 | 양의 방향, -π~π |
| 라이다 갱신 주기 | 실차 장치·드라이버에 따름 | 10Hz 고정 설정 |
| 센서 잡음·무응답 | 실제 환경·재질에 따라 발생 | 실제 잡음·재질별 무응답 특성을 별도로 재현하지 않음 |
| 라이다 드라이버 | 실제 센서 드라이버 | Gazebo GPU LiDAR + ROS 브리지 |
| 지도 작성 알고리즘 | Cartographer 2D | 동일 |
| 지도 작성 최대 사용 거리 | 기본 real 프로파일 3.5m | 기본 8m, 실행 인자로 최대 16m까지 지정 |
| SLAM 최소 사용 거리 | real 프로파일 0.12m | 동일. 단, 모의 센서 자체의 최소 측정 거리는 0.28m |
| 무응답 광선 처리 거리 | real 프로파일 `missing_data_ray_length=1.0m` | 동일 |
| Cartographer odometry 사용 | 사용 | 동일 |
| Cartographer IMU 사용 | 미사용 | 동일 |
| Cartographer 프레임·자세 발행 주기 | tracking: base_link, published/odom: odom, 0.05초 | 동일 |
| 바퀴 구동·odometry | 실제 하드웨어 드라이버 | Gazebo DiffDrive, odometry 발행 50Hz |
| 시간 기준 | 실제 시계 | 시뮬레이션 시계, `use_sim_time=true` |
| 저장 지도 위치 추정 | AMCL | 동일, 주요 수치 유지 |
| 로컬 경로 제어 | 원본 Nav2의 MPPI·RPP 설정 | 주요 수치 유지, 선택한 기본 BT는 MPPI 사용 |
| 전역 경로 계획 | 원본에 여러 구성 존재 | 원본의 NavFn + MPPI staging 구성 선택, Lattice planner는 시작하지 않음 |
| 차체 footprint | 실차 비대칭 footprint | 동일 |
| 충돌 판정 영역 | Collision Monitor의 원본 polygons | 동일 |
| Keepout 운영 | 원본에 관련 설정·운영 코드 존재 | 이 예제에서는 Keepout mask·운영 서비스를 실행하지 않음 |
| 속도 명령 경로 | 실차 운용 구성에 따름 | 하네스 명령 선택기 → Collision Monitor → Gazebo |
| 최종 속도 제한 | 원본 제어기·드라이버 설정에 따름 | 추가 명령 선택기에서 전진 0.12m/s, 후진 0.08m/s, 회전 0.3rad/s로 제한 |
| 지도·초기 위치 | 실차 운용 지도와 초기 위치 | 실행 시 저장 지도를 지정, 초기 위치 수동 지정 또는 명시적 인자 전달 |
| Navigation 시작 조건 | 실차 실행 구성에 따름 | 최신 map→base_footprint TF가 준비된 후 활성화 |
| 관성·접촉·마찰 | 실제 물리 특성 | Gazebo 실행을 위한 모델링 값. 실측 동역학 보정값은 아님 |

라이다의 실측 측정점 수와 각도 순서는 원본의 `jdamr_cube_navigation/evaluation/real_scan_reference_g4.json` 기록에 근거합니다. 모든 실차 운용 조건에서 동일하다는 의미는 아닙니다.

## 지도 작성 거리 변경

기본 real 프로파일의 원본 `max_range=3.5`는 보존합니다. 지도 작성 launch가 임시 실행용 Lua를 생성해 최대 사용 거리만 덮어씁니다. 기본값은 8m이며, launch 종료 시 임시 파일을 제거합니다.

```bash
# 기본 8m
ros2 launch jdamr_cube_harness three_tables_mapping.launch.py

# 12m 사용
ros2 launch jdamr_cube_harness three_tables_mapping.launch.py slam_max_range:=12.0

# 실차 원본과 같은 3.5m 제한
ros2 launch jdamr_cube_harness three_tables_mapping.launch.py slam_max_range:=3.5
```

허용 범위는 0.28m 초과, 16m 이하입니다. 변경하려면 지도 작성 launch를 종료하고 다시 시작합니다. `slam_profile:=corridor` 선택 시에도 이 거리 인자를 적용하며, 나머지 설정은 선택한 원본 프로파일을 따릅니다. 위 표의 SLAM 수치는 기본 `real` 프로파일 기준입니다.

이 거리 변경은 **지도 작성용 Cartographer에만 적용**됩니다. 저장 지도로 주행하는 AMCL·costmap의 거리 파라미터는 실차 원본 값을 유지합니다.

## Navigation 연결에서 변경한 부분

- 하네스의 Nav2 명령과 미세 제어 명령을 선택하는 mux를 Collision Monitor 앞에 추가했습니다. 두 명령 모두 최종 충돌 검사를 거칩니다.
- 선택한 원본 staging BT에 필요한 goal checker ID를 원본 PositionGoalChecker 설정에 연결했습니다.
- 실행 시계, 파일 경로, 속도 토픽과 초기 위치 지정 방식을 시뮬레이션에 맞췄습니다.
- MPPI 수치, costmap footprint, Collision Monitor의 StopZone 등 원본 충돌 영역은 유지했습니다.

현재 구성은 실차 주행 설정을 활용한 시뮬레이션입니다. 실제 센서 잡음, 바퀴 슬립, 하중 변화까지 동일하게 재현한 모델은 아닙니다.

## 관련 파일

- [실행 방법](../jdamr_harness_readme.md)
- [이식 기준 및 ros_dd와의 비교](SLAM_COMPARISON.md)
- [원본 파일 해시 기록](IMPORT_PROVENANCE.json)
- [실행 검증 기록](VALIDATION.md)
- [모의 로봇·라이다](jdamr_cube_description/urdf/new_base_sim.urdf)
- [원본 실차 Nav2 설정 사본](jdamr_cube_harness/config/upstream_new_base_nav2.yaml)
- [Navigation 실행 설정 변환](jdamr_cube_harness/jdamr_cube_harness/parameters.py)
- [지도 작성 거리 설정 변환](jdamr_cube_harness/jdamr_cube_harness/mapping_parameters.py)
