"""선택 기능: 미세 정렬과 후퇴에 쓸 저속을 계산합니다. ROS 통신은 하지 않습니다."""
import math


def wrap(angle):
    """각도 차이를 -pi ~ pi 범위로 바꿉니다."""
    return math.atan2(math.sin(angle), math.cos(angle))


def control(pose, target, reverse=False, xy_tolerance=0.025, yaw_tolerance=0.04):
    """반환값: ((전진 속도 m/s, 회전 속도 rad/s), 도착 여부)."""
    dx = target.x - pose.x
    dy = target.y - pose.y
    distance = math.hypot(dx, dy)

    # 위치에 도착했다면 마지막으로 바라보는 방향을 맞춥니다.
    if distance <= xy_tolerance:
        angle_error = wrap(target.yaw - pose.yaw)
        angular = max(-0.25, min(0.25, angle_error))
        reached = abs(angle_error) <= yaw_tolerance
        return (0.0, angular), reached

    # 먼저 목표 위치를 향하도록 회전합니다. 후퇴는 반대 방향을 바라봅니다.
    heading = math.atan2(dy, dx)
    if reverse:
        heading = heading + math.pi
    angle_error = wrap(heading - pose.yaw)
    angular = max(-0.25, min(0.25, angle_error))

    # 방향이 맞을 때만 직선 이동합니다.
    linear = 0.0
    if abs(angle_error) < 0.15:
        linear = min(0.06, 0.5 * distance)
    if reverse:
        linear = -linear
    return (linear, angular), False
