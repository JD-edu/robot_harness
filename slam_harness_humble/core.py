"""검증된 계획의 유한 재시도, 후퇴, 실패 분기를 실행합니다."""
from dataclasses import dataclass, field

from .locations import Pose, Landmark, load_registry
from .llm_planner import LLMPlanner, validate_plan
from .fine_controller import wrap, control

RETRYABLE = frozenset(('aborted', 'rejected', 'timeout', 'stalled'))
ORIGIN = Pose(0.0, 0.0, 0.0)


@dataclass
class MissionResult:
    success: bool
    completed: list = field(default_factory=list)
    failed_at: str = ''
    reason: str = ''
    retreat_succeeded: bool = False
    warnings: list = field(default_factory=list)
    events: list = field(default_factory=list)


class Mission:
    def __init__(self, registry, skills, retries=1, on_arrival=None, alignment='optional'):
        if type(retries) is not int or not 0 <= retries <= 3:
            raise ValueError('retries must be 0..3')
        if alignment not in ('optional', 'required', 'skip'):
            raise ValueError('alignment must be optional, required, or skip')
        self.registry = registry
        self.skills = skills
        self.retries = retries
        self.on_arrival = on_arrival
        self.alignment = alignment

    def move_with_retry(self, target):
        # 기존 단독 재시도 API도 유지합니다.
        for _ in range(self.retries + 1):
            outcome = self.skills.move_to(target)
            if outcome not in RETRYABLE:
                return outcome
        return outcome

    def record(self, result, **event):
        result.events.append(event)
        logger = getattr(self.skills, 'get_logger', None)
        if logger is not None:
            logger().info('mission: ' + str(event))

    def approach(self, step, result):
        """각 라운드는 최초 성공 시 종료하고 실패한 경우에만 다음으로 진행합니다."""
        target = step['target']
        pose = ORIGIN if target == 'origin' else self.registry[target].approach
        for round_index in range(step['restart_count'] + 1):
            for attempt in range(step['attempts']):
                outcome = self.skills.move_to(pose)
                self.record(result, skill='move_to', target=target,
                            round=round_index + 1, attempt=attempt + 1, outcome=outcome)
                if outcome == 'succeeded' or outcome not in RETRYABLE:
                    return outcome, True
            if round_index < step['restart_count']:
                outcome = self.skills.backoff(step['backoff_m'])
                self.record(result, skill='backoff', target=target,
                            distance_m=step['backoff_m'], round=round_index + 1, outcome=outcome)
                result.retreat_succeeded = outcome == 'succeeded'
                if outcome != 'succeeded':
                    # 후퇴 실패 시 다음 이동이나 대체 목표 이동을 허용하지 않습니다.
                    return 'backoff:' + outcome, False
        return outcome, True

    def finish_visit(self, name, result):
        # 원점에는 테이블 정렬을 적용하지 않습니다.
        if name != 'origin' and self.alignment != 'skip':
            landmark = self.registry[name]
            outcome = self.skills.align_to(landmark.align)
            if outcome != 'succeeded':
                unsafe = outcome in ('unsafe', 'canceled', 'unknown', 'gate_unavailable', 'unavailable')
                if self.alignment == 'required' or unsafe:
                    result.failed_at = name
                    result.reason = 'align_to:' + outcome
                    if not unsafe:
                        retreat_result = self.skills.retreat_to(landmark.retreat)
                        result.retreat_succeeded = retreat_result == 'succeeded'
                    return False
                result.warnings.append({'waypoint': name, 'skill': 'align_to', 'reason': outcome})
        if self.on_arrival is not None:
            try:
                self.on_arrival(name)
            except Exception as error:
                result.failed_at = name
                result.reason = 'arrival callback: ' + str(error)
                return False
        result.completed.append(name)
        return True

    def run(self, plan):
        raw = {'waypoints': plan} if isinstance(plan, list) else plan
        checked = validate_plan(raw, self.registry)
        if isinstance(checked, list):
            checked = validate_plan({'steps': [
                {'target': name, 'attempts': self.retries + 1,
                 'restart_count': 0, 'backoff_m': 0, 'on_failure': ''}
                for name in checked
            ]}, self.registry)
        result = MissionResult(success=False)
        for step in checked['steps']:
            name = step['target']
            outcome, navigation_outcome = self.approach(step, result)
            if outcome != 'succeeded':
                fallback = step['on_failure']
                if navigation_outcome and outcome in RETRYABLE and fallback:
                    result.warnings.append({'waypoint': name, 'skill': 'move_to',
                                            'reason': outcome, 'fallback': fallback})
                    fallback_step = dict(target=fallback, attempts=1, restart_count=0,
                                         backoff_m=0, on_failure='')
                    self.record(result, skill='fallback', target=fallback, failed_target=name)
                    outcome, _ = self.approach(fallback_step, result)
                    name = fallback
                if outcome != 'succeeded':
                    result.failed_at = name
                    result.reason = outcome if outcome.startswith('backoff:') else 'move_to:' + outcome
                    return result
            if not self.finish_visit(name, result):
                return result
        result.success = True
        return result
