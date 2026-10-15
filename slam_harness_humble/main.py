"""실행 시작: 옵션 읽기 → 좌표 읽기 → LLM 계획 받기 → ROS 미션 실행."""
import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from .locations import load_registry
from .llm_planner import LLMPlanner, validate_plan
from .core import Mission


def registry_path():
    """소스 실행과 ROS 패키지 설치 실행에서 좌표 파일을 찾습니다."""
    local = Path(__file__).parent / 'config' / 'locations.yaml'
    if local.exists():
        return str(local)
    from ament_index_python.packages import get_package_share_directory
    package_folder = Path(get_package_share_directory('slam_harness'))
    return str(package_folder / 'config' / 'locations.yaml')

'''
python3 -m slam_harness_humble.main '테이블 1번 들렀다가 3번으로 가' \
  --base-url http://127.0.0.1:8080/v1 \
  --model qwen3-8b \
  --ros-args -p use_sim_time:=true
'''
def read_options(args):
    """하네스 옵션과 --ros-args 뒤의 ROS 옵션을 구분합니다."""
    parser = argparse.ArgumentParser(description='Natural language → semantic plan → Nav2 → table alignment')
    parser.add_argument('command', nargs='?', default='')
    parser.add_argument('--locations', default=registry_path())
    parser.add_argument('--plan-json', help='Explicit JSON plan; bypass LLM for reproducible tests')
    parser.add_argument('--base-url', default='http://127.0.0.1:8080/v1')
    parser.add_argument('--model', default='qwen3-8b')
    parser.add_argument('--dry-run', action='store_true', help='Validate/print plan without ROS or motion')
    parser.add_argument('--nav-timeout', type=float, default=120.)
    parser.add_argument('--align-timeout', type=float, default=25.)
    parser.add_argument('--retreat-timeout', type=float, default=40.)
    parser.add_argument('--retries', type=int, choices=range(4), default=1,
                        help='Default extra attempts when natural language omits a count; explicit steps override it')
    parser.add_argument('--alignment', choices=('optional', 'required', 'skip'), default='optional',
                        help='optional: continue after alignment failure (default); required: retreat and stop; skip: Nav2 only')
    if args is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(args)
    split = len(argv)
    if '--ros-args' in argv:
        split = argv.index('--ros-args')
    options = parser.parse_args(argv[:split])
    ros_args = argv[split:]
    for timeout in (options.nav_timeout, options.align_timeout, options.retreat_timeout):
        if not 0 < timeout <= 600:
            parser.error('timeouts must be finite and within (0, 600] seconds')
    if not options.plan_json and not options.command.strip():
        parser.error('command or --plan-json is required')
    return options, ros_args


def create_plan(options, registry):
    """직접 JSON을 지정하면 LLM 없이 실행할 수 있습니다."""
    if options.plan_json:
        return validate_plan(options.plan_json, registry)
    planner = LLMPlanner(base_url=options.base_url, model=options.model)
    return planner.plan(options.command, registry, default_attempts=options.retries + 1)


def run_ros_mission(options, ros_args, registry, plan):
    # dry-run은 ROS 설치 없이도 쓸 수 있도록 ROS import를 이 함수에 둡니다.
    import rclpy
    from .ros_backend import ROSSkills

    rclpy.init(args=ros_args)
    node = ROSSkills(options.nav_timeout, options.align_timeout, options.retreat_timeout)
    try:
        mission = Mission(
            registry=registry,
            skills=node,
            retries=options.retries,
            on_arrival=node.on_arrival,
            alignment=options.alignment,
        )
        result = mission.run(plan)
        for warning in result.warnings:
            node.get_logger().warning(
                f"{warning['waypoint']}: 미세 정렬 {warning['reason']}, 방문은 완료로 처리")
        # asdict는 데이터 클래스의 결과를 JSON 출력용 사전으로 바꿉니다.
        print(json.dumps(asdict(result), ensure_ascii=False), flush=True)
        if result.success:
            return 0
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        # 성공/실패/Ctrl+C 어느 경우에도 정지와 노드 정리를 실행합니다.
        try:
            if rclpy.ok():
                node.shutdown_motion()
        finally:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


def main(args=None):
    # 처음 읽을 때는 이 다섯 단계부터 살펴보세요.
    # 1. 터미널 옵션 읽기
    options, ros_args = read_options(args)
    # 2. 테이블 좌표 읽기
    registry = load_registry(options.locations)
    # 3. LLM 계획 생성 및 검증 (아직 로봇을 움직이지 않습니다.)
    try:
        plan = create_plan(options, registry)
    except ValueError as error:
        print(f'[ERROR] 실행할 수 없는 계획입니다: {error}', file=sys.stderr)
        return 2
    print(json.dumps(plan if isinstance(plan, dict) else {'waypoints': plan},
                     ensure_ascii=False), flush=True)
    # 4. 계획 확인만 할 때는 여기서 종료
    if options.dry_run:
        return 0
    # 5. Nav2를 이용한 미션 실행
    return run_ros_mission(options, ros_args, registry, plan)


if __name__ == '__main__':
    raise SystemExit(main())
