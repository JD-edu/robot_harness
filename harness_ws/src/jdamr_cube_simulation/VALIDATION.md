# JDAMR Cube Three Tables 검증 (2026-10-21)

## 소프트웨어·출처 검증

- 깨끗한 환경에서 시스템 `/opt/ros/jazzy`만 source하고 전체 11개 패키지 빌드 성공.
- JDAMR 어댑터/물리 제원/원본 무변경/명령 timeout/제어권 전환/미션 인자 전달 테스트 11개 통과.
- 기존 ros_dd 하네스 회귀 테스트 55개 통과.
- Gazebo가 new_base_sim.urdf를 SDFormat으로 변환·검증하는 검사 통과.
- 원본 실차 URDF의 모든 관절·고정 TF 및 바퀴 반경 0.0329m·중심 간격 0.510m 유지 확인.
- 원본 current Nav2 footprint·MPPI 수치·StopZone polygon과 실행 어댑터 값 일치 확인.
- 원본에서 가져온 불변 파일은 IMPORT_PROVENANCE.json의 SHA-256과 일치.
- bimanual-robot 원본 및 실차 드라이버·서비스는 변경하거나 실행하지 않음.

## 지도 작성과 저장

기존 실행과 격리한 ROS_DOMAIN_ID=94, GZ_PARTITION=jdamr_three_tables_validation_94를 사용했습니다.

- JDAMR current 하단 차체·G4 장착 TF·모의 10Hz LaserScan·50Hz odometry 발행.
- 원본 `jdamr_cube_2d_real.lua`를 그대로 사용하고 use_sim_time만 Gazebo 시계로 설정.
- 지도 작성 그래프에 Nav2·AMCL·Collision Monitor가 없는 것을 확인.
- odometry 피드백으로 (0.9,0), (-0.9,0), (0,0) 관측 이동을 수행.
- Cartographer가 중단 없이 스캔과 odometry를 처리하고 171×91셀 지도를 생성.
- `/tmp/jdamr_three_tables_94/site_map.yaml`과 PGM 저장 성공.
- 이 검증 관측은 모든 방 벽을 충분히 스캔한 지도 품질 평가가 아니라, 세 탁자 접근 영역의 기능 확인입니다.

## 저장 지도 하네스 내비게이션

지도 작성을 종료한 뒤 동일한 저장 YAML을 명시하여 새 JDAMR Gazebo와 AMCL·Nav2를 시작했습니다.

- Cartographer 없이 map_server·AMCL 및 Nav2 lifecycle 활성화 성공.
- NavFn planner, MPPI와 RPP controller, Collision Monitor 활성화 확인.
- 검증용 지도에서 (0,0,0) 초기 위치를 명시 전달. 다른 지도에 대한 기본 좌표라고 가정하지 않음.
- 로컬 Qwen3 8B에 “테이블 1번, 2번, 3번 순서로 방문해”를 실제 요청.
- `jdamr_cube_harness mission --alignment skip`으로 table_1 → table_2 → table_3 모두 최초 시도에 방문 성공.

```json
{"success":true,"completed":["table_1","table_2","table_3"],"failed_at":"","reason":"","warnings":[]}
```

## 미세 정렬과 속도 경로

- 최초 25초 제한의 table_3 정렬은 시간 초과됐고, 후퇴는 성공했습니다.
- 원본 위치 중심 staging 뒤의 저속 방향 정렬을 고려해 JDAMR wrapper 기본 정렬 제한시간을 60초로 분리했습니다.
- 사용자 지정 제한시간 보존 회귀 검사 추가.
- 다시 table_3를 `alignment=required`로 방문하고 정렬 성공.
- selected_cmd_vel → Collision Monitor → cmd_vel 관측에서 속도 전달 확인.
- ROS 그래프상 /cmd_vel 발행자는 collision_monitor 하나, 그 앞단 selected_cmd_vel 발행자는 jdamr_velocity_mux 하나임을 확인.
- 정렬 전후 /map 점유 데이터 SHA-256이 동일함을 확인.

```json
{"success":true,"completed":["table_3"],"failed_at":"","reason":"","warnings":[]}
```

검증 완료 후 이 작업에서 시작한 지도 작성·내비게이션·관측 노드는 모두 종료했습니다.
실제 하드웨어 주행, 하중/양팔/카메라 동작, 센서 잡음·슬립, 외부 실측 정확도는 검증하지 않았습니다.
Gazebo용 관성·마찰·캐스터 접촉 모델은 실차의 동역학 보정 결과가 아닙니다.

임시 로그:

- `/tmp/jdamr_mapping_94.log`, `/tmp/jdamr_mapping_survey.log`
- `/tmp/jdamr_navigation_94.log`, `/tmp/jdamr_three_table_mission.log`
- `/tmp/jdamr_alignment_mission.log` (최초 제한시간 실패 및 후퇴)
- `/tmp/jdamr_alignment_60_mission.log`, `/tmp/jdamr_alignment_probe.log`
- `/tmp/jdamr_alignment_observations.jsonl`

## 2026-10-22: 지도 작성 관측 거리 확장

- 모의 G4 센서 0.28~16m는 유지하고 Cartographer의 시뮬레이션 기본 max_range를 3.5m에서 8m로 확장.
- `slam_max_range` 인자로 0.28m 초과~16m 이하 지정 가능. 원본 real/corridor Lua 사본의 해시는 유지.
- jdamr_cube_harness 재빌드 성공, 단위 테스트 13개 통과.
- 별도 ROS_DOMAIN_ID=95 / GZ_PARTITION=jdamr_range_validation_95에서 headless 지도 작성 검증.
- 정지 상태 /scan range_max=16m, 유효 반사 최대 약 5.526m 수신. /map 169×169 셀 생성, 원점 3.6m 밖 점유 셀 422개 확인.
- 시험 launch만 종료했으며 사용자 실행 중인 시뮬레이션은 유지.
