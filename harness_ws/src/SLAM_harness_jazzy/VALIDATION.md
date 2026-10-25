> 실행 방법은 [harness_readme.md](../harness_readme.md)를 참고하세요.
> 이 문서는 과거 검증 기록과 아래의 저장 지도 기본 운용 변경 검증을 보관합니다.

# Jazzy 검증 기록 (2026-10-19)

환경: 로컬 ROS 2 Jazzy, Gazebo Harmonic, Python 3.12,
`~/robot_harness/harness_ws/src/ros_dd_simulation`의 three_tables 월드와 Cartographer/Nav2.
Qwen3 8B Q4_K_M은 기존 `http://127.0.0.1:8080/v1` llama.cpp 서버를 사용했습니다.

## 빌드·회귀 테스트

- `colcon build --base-paths .` 패키지 빌드 성공.
- 단위·ROS 메시지 컴포넌트·Jazzy 통합 설정 테스트 **50개 통과**.
- 계획 전체 검증, 방문 순서, 실패 분기, 총 시도/추가 라운드 수, 후퇴 좌표,
  취소 결과 확인, 게이트 제어권/센서/명령 타임아웃 검사 포함.
- Nav2 lifecycle 비활성 또는 map TF 미준비 시 이동을 시작하지 않음 확인.
- CLI의 준비 대기시간과 세 가지 동작 제한시간 전달을 회귀 검사.
- 실제 `RewrittenYaml`로 기존 YAML에 없는 AMCL `set_initial_pose`,
  `initial_pose.x/y/z/yaw`가 올바르게 추가되는지 검사.
- Jazzy의 controller/behavior/velocity smoother가 `Twist`로 설정되는지 검사.

## 온라인 SLAM + 자연어 실제 주행

기존 실행 환경과 분리한 `ROS_DOMAIN_ID=86`,
`GZ_PARTITION=slam_harness_jazzy_validation_86`에서 GUI 없이 실행했습니다.

- 전용 launch에서 Gazebo 로봇, Cartographer `/map`/TF, Nav2 lifecycle 활성화 성공.
- 실제 ROS 그래프에서 `/cmd_vel` publisher가 `slam_velocity_gate` 하나임을 확인.
- `controller_server`/`behavior_server` → `/cmd_vel_nav` → `velocity_smoother`
  → `/slam_harness/nav_cmd_vel` → 게이트 → `/cmd_vel` → `ros_gz_bridge` 연결 확인.
- 로컬 Qwen3에 “테이블 1번 들렀다가 3번으로 가”를 실제 요청.
- 생성된 계획으로 `--alignment required` 미션 실행:
  table_1 접근·미세 정렬 → table_3 접근·미세 정렬 → 도착 콜백 모두 성공.

```json
{"success":true,"completed":["table_1","table_3"],"failed_at":"","reason":"","retreat_succeeded":false,"warnings":[]}
```

## 저장 지도 + AMCL 실제 주행

`ROS_DOMAIN_ID=88`, `GZ_PARTITION=slam_harness_jazzy_validation_88`에서 실행했습니다.

- `mode:=saved_map`, `~/robot_harness/harness_ws/maps/three_tables/map.yaml` 사용.
- 이 지도에 대해 `set_initial_pose:=true initial_x:=0 initial_y:=0 initial_yaw:=0` 전달.
- Cartographer 없이 map_server/AMCL 및 `Nav2 ready` 활성화 확인.
- 명시적 JSON 계획 `table_2`, `--alignment skip`으로 실제 Nav2 방문 성공.

```json
{"success":true,"completed":["table_2"],"failed_at":"","reason":"","retreat_succeeded":false,"warnings":[]}
```

위 초기 위치의 성공은 이 저장 지도에 대한 결과입니다. 다른 지도에서 같은 좌표를
자동 재사용하지 않습니다. 검증을 위해 시작한 launch는 검증 후 종료했습니다.

## 범위와 한계

GUI/RViz 화면과 실제 하드웨어는 검증하지 않았습니다.
조건부 실패·후퇴 경로는 단위/컴포넌트 테스트로 검사했으며 이번 Gazebo 검증에서는
장애물을 강제로 배치해 전체 복구 경로를 재현하지 않았습니다.
미세 정렬은 SLAM 추정 위치를 기준으로 하며 외부 계측으로 실제 오차를 측정하지 않았습니다.
LLM 실응답 검증은 해당 문장의 실행 결과이며 모든 자연어 표현의 해석을 보장하지 않습니다.

상세 런타임 로그는 이번 세션의 `/tmp/slam_jazzy_online.log`,
`/tmp/slam_jazzy_mission.log`, `/tmp/slam_jazzy_saved88.log`,
`/tmp/slam_jazzy_saved_mission.log`에 있습니다 (임시 파일).


## 저장 지도 기본 운용으로 변경 후 검증

- `three_tables_harness.launch.py` 기본값을 `saved_map`으로 변경했습니다.
- 워크스페이스의 three_tables YAML/PGM을 패키지에 설치하고 기본 경로로 사용합니다.
- 테스트 53개 통과: 저장 지도 기본 분기, 설치 지도 일치, 지도 누락 시 노드 시작 전 차단 포함.
- `/opt/ros/jazzy`만 사용한 깨끗한 환경에서 빌드했습니다.
- 격리된 domain 91 / GZ partition `harness_saved_default_91`에서 mode/map 인수 없이 실행했습니다.
- map_server가 설치 지도를 읽고, Cartographer 없이 AMCL이 수동 초기 위치를 기다리는 것을 확인했습니다.
- `/initialpose`로 map 기준 (0,0,0)을 전달한 뒤 Nav2 활성화 성공.
- JSON table_1 → table_3 미션을 alignment=required로 실행해 두 테이블 접근·미세 정렬 모두 성공.
- 주행 전후 `/map`의 크기·해상도·점유 데이터 SHA-256이 동일함을 확인했습니다.
- GUI/RViz 화면과 실제 하드웨어는 이번 검증에 포함하지 않았습니다.
- 검증에 시작한 시뮬레이션은 종료했습니다.

로그: `/tmp/harness_saved_default.log`, `/tmp/harness_saved_default_mission.log` (임시 파일).


## 지도 작성부터 시작하는 단계 분리 검증 (2026-10-20)

현재 절차는 먼저 지도를 생성·저장하고, 지도 작성 종료 후 운용 launch에 그 YAML을 명시합니다.
이전 기록의 설치 지도 기본 선택 방식은 더 이상 사용하지 않습니다.

- `three_tables_mapping.launch.py`: Gazebo·Cartographer·지도 작성용 RViz만 시작하도록 유지하고 단계 안내를 추가했습니다.
- 하네스 기본 모드는 saved_map이며 map 인수 누락 시 지도 작성부터 진행하라는 오류로 종료합니다.
- 패키지 빌드에서 기존 지도 파일 설치 의존성을 제거했습니다. 새 지도는 재빌드 없이 직접 읽습니다.
- 하네스 테스트 55개, 월드·지도 검사 12개 통과 및 전체 8개 패키지 빌드 성공.
- 격리 domain 92 / GZ partition `three_tables_map_first_92`에서 실제 지도 작성 launch 실행.
- Nav2·AMCL·게이트 없는 지도 작성 그래프 확인 후 제자리 회전 관측으로 새 지도를 작성했습니다.
- `/tmp/three_tables_map_first_92/site_map.yaml` 및 PGM 저장 성공.
- 지도 작성 중 운용 시작 시 충돌 검사로 차단됨을 확인했습니다.
- 지도 작성 launch를 완전히 종료한 뒤 새 YAML을 지정해 하네스 launch 실행.
- map_server의 yaml_filename 파라미터가 이번에 저장한 파일 경로와 일치함을 확인했습니다.
- 초기 위치 전달 후 Qwen3 자연어 계획으로 table_1 → table_3 방문 성공 (alignment=skip).
- 주행 전후 YAML·PGM·점유 지도 SHA-256이 모두 동일함을 확인했습니다.
- 실제 하드웨어와 GUI 화면 검증은 포함하지 않았습니다. 검증용 시뮬레이션은 종료했습니다.

로그: `/tmp/three_tables_mapping_92.log`, `/tmp/three_tables_map_first_save.log`,
`/tmp/three_tables_stage_conflict.log`, `/tmp/three_tables_map_first_navigation.log`,
`/tmp/three_tables_map_first_mission.log` (임시 파일).


## 탁자 식별 표시 추가 검증

- table_1 빨강, table_2 초록, table_3 파랑으로 변경하고 상판 및 양면 번호판에 숫자를 추가했습니다.
- 탁자 모델 위치와 기존 충돌체는 유지했습니다. 번호 표식은 시각 요소이며 LiDAR보다 높습니다.
- Gazebo SDF 문법 검사 통과, 월드·센서 회귀 검사 6개 통과, ros_dd_gazebo 빌드 성공.
- Gazebo Ogre2 headless 카메라로 실제 렌더링해 1/2/3 표시를 확인했습니다.
- 미리보기: `/tmp/three_table_identity_preview.png` (임시 파일).
- 접근·정렬 좌표와 주행 제어 설정은 변경하지 않았습니다.
