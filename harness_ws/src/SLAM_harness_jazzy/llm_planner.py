"""자연어를 검증 가능한 유한 재시도·실패 분기 계획으로 변환합니다."""
import json
import math
import urllib.request

STEP_FIELDS = {'target', 'attempts', 'restart_count', 'backoff_m', 'on_failure'}
MAX_MOVES = 80


def targets_for(registry):
    return list(registry) + ['origin']


def validate_plan(raw, registry):
    """전체 계획을 이동 전에 검사합니다. 기존 waypoints 형식도 지원합니다."""
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict):
        raise ValueError('plan must be an object')
    if set(data) == {'waypoints'}:
        names = data['waypoints']
        if not isinstance(names, list) or not 1 <= len(names) <= 20:
            raise ValueError('waypoints must contain 1..20 entries')
        if any(not isinstance(name, str) or name not in targets_for(registry) for name in names):
            raise ValueError('plan contains an unregistered landmark')
        return list(names)
    if set(data) != {'steps'}:
        raise ValueError('plan must contain exactly steps or waypoints')
    steps = data['steps']
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        raise ValueError('steps must contain 1..20 entries')
    budget = 0
    checked = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != STEP_FIELDS:
            raise ValueError('each step requires target, attempts, restart_count, backoff_m, on_failure')
        target, fallback = step['target'], step['on_failure']
        if not isinstance(target, str) or target not in targets_for(registry):
            raise ValueError('unknown target')
        if not isinstance(fallback, str) or fallback not in ['', *targets_for(registry)]:
            raise ValueError('unknown failure target')
        if fallback == target:
            raise ValueError('failure target must differ from target')
        attempts, restarts, distance = step['attempts'], step['restart_count'], step['backoff_m']
        if type(attempts) is not int or not 1 <= attempts <= 4:
            raise ValueError('attempts must be 1..4 total attempts per round')
        if type(restarts) is not int or not 0 <= restarts <= 3:
            raise ValueError('restart_count must be 0..3 additional rounds')
        if type(distance) not in (int, float) or not math.isfinite(distance):
            raise ValueError('backoff_m must be finite')
        if restarts and not 0.1 <= distance <= 1.5:
            raise ValueError('restarts require backoff_m within 0.1..1.5')
        if not restarts and distance != 0:
            raise ValueError('backoff_m must be 0 without restarts')
        budget += attempts * (restarts + 1) + restarts + bool(fallback)
        checked.append(dict(step))
    if budget > MAX_MOVES:
        raise ValueError(f'plan exceeds {MAX_MOVES} motion operations')
    return {'steps': checked}


class LLMPlanner:
    def __init__(self, base_url='http://127.0.0.1:8080/v1', model='qwen3-8b', timeout=60):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout

    def create_schema(self, registry):
        return {
            'type': 'object',
            'properties': {'steps': {
                'type': 'array', 'minItems': 0, 'maxItems': 20,
                'items': {
                    'type': 'object',
                    'properties': {
                        'target': {'type': 'string', 'enum': targets_for(registry)},
                        'attempts': {'type': 'integer', 'minimum': 1, 'maximum': 4},
                        'restart_count': {'type': 'integer', 'minimum': 0, 'maximum': 3},
                        'backoff_m': {'type': 'number', 'minimum': 0, 'maximum': 1.5},
                        'on_failure': {'type': 'string', 'enum': ['', *targets_for(registry)]},
                    },
                    'required': ['target', 'attempts', 'restart_count', 'backoff_m', 'on_failure'],
                    'additionalProperties': False,
                },
            }},
            'required': ['steps'], 'additionalProperties': False,
        }

    def plan(self, command, registry, default_attempts=2):
        schema = self.create_schema(registry)
        system_prompt = (
            'You translate Korean robot commands into JSON matching the supplied schema. '
            'Return JSON only. Never invent targets, coordinates, or actions. '
            'Available targets: ' + ', '.join(targets_for(registry)) + '. '
            'Preserve sequential visit order and repetitions. '
            'Each step attempts navigation to target; stop that step on first success. '
            'attempts is TOTAL attempts per round including the first (1..4). '
            f'When unspecified use attempts={default_attempts}. '
            'restart_count is ADDITIONAL rounds after the initial round (0..3). '
            'After all attempts in a round fail, back off backoff_m meters in the robot backward '
            'direction, then start the next round. Back off only BETWEEN rounds, never after success '
            'or after the final exhausted round. Without restarts set restart_count=0 and backoff_m=0. '
            'on_failure is a fallback target visited ONCE only if ALL rounds fail. '
            'Use empty string for no fallback; do not also add a fallback as an unconditional step. '
            'If the primary target succeeds, skip its fallback. '
            'For three total attempts use attempts=3. For two retries after first use attempts=3. '
            'For 처음부터 다시 2번 after 3 failed attempts use attempts=3, restart_count=2. '
            'Interpret 원점, 원정, 원점으로, 출발점, home as origin (map x=0,y=0,yaw=0). '
            'For 뒤로 1미터 물러나서 use backoff_m=1.0 with the requested restart_count. '
            'This backward motion means the current ROBOT backward direction, not the other side of a table. '
            'Reject commands explicitly asking for a different table-relative retreat geometry, '
            'unsupported actions, ambiguous conditions, out-of-range counts or distances. '
            'Reject by returning {"steps": []}; never drop an unsupported condition. '
            'Example: 테이블 1에 접근하는데 실패하면 3번까지 시도하고 다 실패하면 테이블 3으로 바로 갑니다 '
            '=> {"steps":[{"target":"table_1","attempts":3,"restart_count":0,"backoff_m":0,"on_failure":"table_3"}]}. '
            'Example: 로봇을 원정으로 이동시켜주세요 '
            f'=> {{"steps":[{{"target":"origin","attempts":{default_attempts},"restart_count":0,"backoff_m":0,"on_failure":""}}]}}. '
            'Example: 테이블 1번에 3번 시도했는데 결국 실패하면 뒤로 1미터 물러나서 처음부터 다시 시도 2번 '
            '=> {"steps":[{"target":"table_1","attempts":3,"restart_count":2,"backoff_m":1,"on_failure":""}]}. '
            'Understand ordinary Korean spelling errors without changing counts or conditional meaning.'
        )
        body = {'model': self.model, 'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': command},
        ], 'stream': False}
        if self.base_url.endswith('/v1'):
            path = '/chat/completions'
            body['temperature'] = 0
            body['chat_template_kwargs'] = {'enable_thinking': False}
            body['response_format'] = {
                'type': 'json_schema',
                'json_schema': {'name': 'navigation_plan', 'strict': True, 'schema': schema},
            }
        else:
            path = '/api/chat'
            body['format'] = schema
            body['think'] = False
            body['options'] = {'temperature': 0}
        request = urllib.request.Request(
            self.base_url + path, data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.load(response)
        raw = (result['choices'][0]['message']['content'] if path == '/chat/completions'
               else result['message']['content'])
        return validate_plan(raw, registry)
