# 검증 기록 (2026-10-14)

환경: 로컬 ROS 2 Humble, Gazebo Classic, 설치된 ros_dd_gazebo URDF 및 Cartographer/Nav2.
기존 실행 환경과 분리한 ROS_DOMAIN_ID=73, Gazebo master 포트 11373에서 headless로 검증했습니다.

- Python 단위/컴포넌트 테스트 19개 통과 (`test_slam_harness.py`, `test_slam_ros_components.py`).
- colcon 패키지 빌드 성공.
- 3테이블 월드에서 ros_dd_robot 생성, Cartographer map/TF, Nav2 lifecycle 활성화 확인.
- 명시적 JSON 계획 table_1 → table_3 실행: 각 테이블 Nav2 접근 및 미세 정렬 성공, 도착 콜백 순서 확인.
- 정렬 제한시간 0.05초, 계획 table_3 → table_2 실행: table_3에서 align_to:timeout,
  등록 후퇴 포즈까지 이동 성공, table_2 미실행, 성공 콜백 미실행.

성공 미션 결과:

```json
{"success": true, "completed": ["table_1", "table_3"], "failed_at": "", "reason": "", "retreat_succeeded": false}
```

의도적 정렬 시간 초과 결과:

```json
{"success": false, "completed": [], "failed_at": "table_3", "reason": "align_to:timeout", "retreat_succeeded": true}
```

로컬 LLM HTTP 요청의 schema 및 응답 검증은 mock HTTP 응답으로 검사했습니다.
실제 LLM 서버를 통한 자연어 추론, 실제 하드웨어, Jazzy/Gazebo Harmonic 조합은 이 검증에 포함되지 않습니다.
위치는 SLAM 추정 기준이며 별도의 테이블 관측 센서로 실제 정렬 오차를 측정하지 않았습니다.

## ros2_ws로 시뮬레이션 자산 이전 후 검증

- ros2_ws의 ros_dd_description, ros_dd_gazebo, ros_dd_cartographer, ros_dd_navigation 빌드 성공.
- ros_dd_navigation/three_tables_navigation.launch.py를 domain 74 / Gazebo port 11374에서 headless 실행.
- ros_dd_description URDF로 로봇 생성, SLAM 및 Nav2 전체 lifecycle 활성화 확인.
- robot_harness 소스의 velocity_gate를 모듈로 실행하여 연결 확인.
- robot_harness에서 table_1 미션을 실행하여 Nav2 이동, 미세 정렬 및 도착 콜백 성공 확인.
- 기존 단위/컴포넌트 테스트 19개 통과.

현재 월드/ROS 설정/launch 소스는 ros2_ws/src/ros_dd_simulation에 있으며,
하네스 Python 코드와 semantic registry만 robot_harness/slam_harness에 있습니다.
이전 /tmp 빌드의 slam_harness simulation.launch.py 대신 ROS 워크스페이스의 새 launch를 사용합니다.

## 기본 Nav2 launch 포함 방식 검증

- three_tables_navigation.launch.py에서 Nav2 navigation_launch.py를 IncludeLaunchDescription으로 실행.
- 새 기본 launch의 Nav2 노드와 lifecycle 활성화 확인 (Humble, domain 75 / Gazebo port 11375).
- /cmd_vel 발행 노드는 slam_velocity_gate만 존재함을 ROS 그래프로 확인.
- velocity_smoother와 behavior_server의 최종 속도는 /slam_harness/nav_cmd_vel로 연결됨을 확인.
- controller_server → /cmd_vel_nav → velocity_smoother 내부 연결 확인.
- table_1 미션을 alignment=skip으로 실행하여 success=true 확인.
- GUI/RViz 화면은 이 headless 검증에서 실행하지 않음.

## 현재 독립 three_tables launch 검증

- 기존 navigation.launch.py 및 Nav2 기본 launch 포함을 제거하고 Cartographer/occupancy grid/Nav2/lifecycle 노드를 직접 선언.
- 원래 navigation.launch.py에 대한 git diff 없음 확인.
- 별도 domain 76 / Gazebo master 11376에서 headless 실행, Cartographer 및 Nav2 활성화 성공.
- /cmd_vel은 게이트만 발행, controller_server/behavior_server 출력이 게이트 입력으로 연결됨을 확인.
- 명시적 JSON table_1 → table_2 미션을 alignment=skip으로 실행하여 두 방문 모두 성공, warnings 없음.
- 현재 실시간 SLAM + AI 방문 계획 구성과 기존 저장 지도 + AMCL 구성을 ROS 워크스페이스 README에 구분하여 기록.
- 이 launch 변경 검증에서는 LLM 추론과 GUI 화면을 실행하지 않음.

## 입문용 코드 정리 후 검증 (2026-10-15)

- 좌표/LLM/미세 제어 계산을 locations.py, llm_planner.py, fine_controller.py로 분리.
- main.py의 실행 순서를 다섯 단계로 정리하고, ROS 콜백을 일반 메서드로 분리.
- 기존 CLI 옵션, 결과 JSON, ROS 토픽/서비스/액션, 정렬 정책 유지.
- 단위/컴포넌트 테스트 32개 통과. Nav2 결과 상태, timeout/stalled 취소,
  취소 중 게이트 오류가 나도 stop 호출, ROS 인자 분리 검증 포함.
- 별도 domain 77 / Gazebo port 11377에서 새 소스의 게이트와 하네스를 실행.
- JSON 계획 table_1 → table_2, alignment=skip 실제 미션 success=true 확인.
- 실제 LLM 서버 추론, 미세 정렬 실제 주행과 GUI 화면은 이 리팩터링 검증에서 재실행하지 않음.


## 조건부 계획 확장 검증 (2026-10-15)

- 현재 소스 `slam_harness_humble`를 대상으로 단위·ROS 메시지 컴포넌트 테스트 47개 통과.
- 총 3회 실패 후 대체 목표 1회, 성공 시 대체 목표 생략, 추가 2라운드의 최대 9회 접근·2회 후퇴 확인.
- 후퇴 실패·취소·미확인 상태·게이트 연결 실패 시 후속 이동 중단 확인.
- 원점 `(0,0,0)` 이동과 정렬 생략 확인.
- 현재 로봇 yaw가 0, pi/2, pi일 때 1m 후퇴 목표 좌표 계산 확인.
- JSON 전체 선검증, 범위/추가 필드/과도한 계획 거부, 기존 waypoints 호환 확인.
- 로컬 `http://127.0.0.1:8080/v1`의 `qwen3-8b`에 사용자가 입력한 세 문장(오타 포함)을 실제 전송.
  생성 계획이 다음과 정확히 일치함을 확인:

| 입력 의도 | Qwen3 생성 계획 |
| --- | --- |
| 테이블 1 총 3회 실패 후 테이블 3 | table_1, attempts=3, restart_count=0, backoff_m=0, on_failure=table_3 |
| “로봇을 원정으로 이동시켜주새요” | origin, attempts=2, restart_count=0, backoff_m=0, on_failure=빈 문자열 |
| 테이블 1 총 3회씩, 뒤로 1m 후 처음부터 다시 2회 | table_1, attempts=3, restart_count=2, backoff_m=1, on_failure=빈 문자열 |

이번 검증에서는 ROS 그래프를 생성하거나 로봇을 움직이지 않았습니다.
새 조건부 계획의 Gazebo/실물 주행 및 후퇴 거리는 아직 실제 주행으로 검증하지 않았습니다.
LLM 실응답 일치는 해당 서버에서 각 문장 1회 확인한 결과이며 모든 표현의 해석을 보장하지 않습니다.
