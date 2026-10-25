"""유한 조건부 계획을 실패 주입으로 검증합니다. 실제 로봇은 사용하지 않습니다."""
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from archvie.slam_harness_humble.core import Mission, Pose, load_registry, validate_plan
from archvie.slam_harness_humble.llm_planner import LLMPlanner
from archvie.slam_harness_humble.main import read_options, create_plan

ROOT = Path(__file__).resolve().parents[1]


def step(target='table_1', attempts=3, restart_count=0, backoff_m=0, on_failure=''):
    return dict(target=target, attempts=attempts, restart_count=restart_count,
                backoff_m=backoff_m, on_failure=on_failure)


class Skills:
    def __init__(self, outcomes=(), backoffs=()):
        self.outcomes = iter(outcomes)
        self.backoffs = iter(backoffs)
        self.calls = []

    def move_to(self, pose):
        self.calls.append(('move', pose))
        return next(self.outcomes)

    def backoff(self, distance):
        self.calls.append(('backoff', distance))
        return next(self.backoffs)

    def align_to(self, pose):
        self.calls.append(('align', pose))
        return 'succeeded'


class RecoveryPlans(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry(ROOT / 'archvie/slam_harness_humble/config/locations.yaml')

    def run_plan(self, spec, outcomes, backoffs=(), alignment='skip'):
        skills = Skills(outcomes, backoffs)
        result = Mission(self.registry, skills, retries=3, alignment=alignment).run({'steps': [spec]})
        return result, skills.calls

    def test_primary_success_skips_fallback(self):
        result, calls = self.run_plan(step(on_failure='table_3'), ['aborted', 'succeeded'])
        self.assertTrue(result.success)
        self.assertEqual(result.completed, ['table_1'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.events[-1]['attempt'], 2)

    def test_three_total_attempts_then_fallback_once(self):
        result, calls = self.run_plan(step(on_failure='table_3'), ['aborted'] * 3 + ['succeeded'])
        self.assertTrue(result.success)
        self.assertEqual(result.completed, ['table_3'])
        self.assertEqual([pose for _, pose in calls],
                         [self.registry['table_1'].approach] * 3 + [self.registry['table_3'].approach])
        self.assertEqual(result.warnings[0]['fallback'], 'table_3')

    def test_failed_fallback_stops(self):
        result, calls = self.run_plan(step(on_failure='table_3'), ['aborted'] * 4)
        self.assertFalse(result.success)
        self.assertEqual(result.failed_at, 'table_3')
        self.assertEqual(len(calls), 4)  # --retries default does not multiply explicit counts

    def test_restart_two_additional_rounds(self):
        result, calls = self.run_plan(step(restart_count=2, backoff_m=1), ['aborted'] * 9,
                                      ['succeeded'] * 2)
        self.assertFalse(result.success)
        self.assertEqual([kind for kind, _ in calls],
                         ['move'] * 3 + ['backoff'] + ['move'] * 3 + ['backoff'] + ['move'] * 3)
        self.assertEqual([value for kind, value in calls if kind == 'backoff'], [1, 1])

    def test_success_in_second_round_stops_early(self):
        result, calls = self.run_plan(step(restart_count=2, backoff_m=1),
                                      ['aborted'] * 3 + ['succeeded'], ['succeeded'])
        self.assertTrue(result.success)
        self.assertEqual(len(calls), 5)

    def test_fallback_only_after_final_round(self):
        result, calls = self.run_plan(step(restart_count=1, backoff_m=1, on_failure='table_3'),
                                      ['timeout'] * 6 + ['succeeded'], ['succeeded'])
        self.assertTrue(result.success)
        self.assertEqual(calls[-1], ('move', self.registry['table_3'].approach))
        self.assertEqual(len(calls), 8)

    def test_cancel_unsafe_and_missing_gate_never_recover(self):
        for outcome in ('canceled', 'unsafe', 'unknown', 'gate_unavailable', 'unavailable'):
            with self.subTest(outcome=outcome):
                result, calls = self.run_plan(step(restart_count=2, backoff_m=1, on_failure='table_3'), [outcome])
                self.assertFalse(result.success)
                self.assertEqual(len(calls), 1)

    def test_backoff_failure_stops_even_with_fallback(self):
        for outcome in ('timeout', 'canceled', 'unsafe', 'gate_unavailable'):
            result, calls = self.run_plan(step(restart_count=2, backoff_m=1, on_failure='table_3'),
                                          ['aborted'] * 3, [outcome])
            self.assertFalse(result.success)
            self.assertEqual(result.reason, 'backoff:' + outcome)
            self.assertEqual(len(calls), 4)

    def test_origin_is_fixed_and_skips_table_alignment(self):
        result, calls = self.run_plan(step(target='origin', attempts=1), ['succeeded'], alignment='required')
        self.assertTrue(result.success)
        self.assertEqual(calls, [('move', Pose(0, 0, 0))])
        self.assertEqual(result.completed, ['origin'])

    def test_validate_all_branches_before_motion(self):
        invalid = [step(target='table_99'), step(attempts=True), step(attempts=0), step(attempts=5),
                   step(restart_count=-1), step(restart_count=4), step(backoff_m=1),
                   step(restart_count=1, backoff_m=0), step(restart_count=1, backoff_m=2),
                   step(backoff_m=float('nan')), step(backoff_m=True),
                   step(on_failure='table_99'), step(on_failure='table_1'),
                   dict(step(), extra=1)]
        for bad in invalid:
            skills = Skills()
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Mission(self.registry, skills).run({'steps': [step(), bad]})
            self.assertEqual(skills.calls, [])
        with self.assertRaises(ValueError):
            validate_plan({'steps': [step(restart_count=3, backoff_m=1)] * 6}, self.registry)

    def test_old_waypoints_and_new_json_cli(self):
        options, _ = read_options(['--plan-json', json.dumps({'steps': [step(target='origin')]}), '--dry-run'])
        self.assertEqual(create_plan(options, self.registry), {'steps': [step(target='origin')]})
        result = Mission(self.registry, Skills(['succeeded']), alignment='skip').run(['origin'])
        self.assertTrue(result.success)

    def test_llm_preserves_conditional_fields_and_default_count(self):
        expected = {'steps': [step(restart_count=2, backoff_m=1)]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return json.dumps({'choices': [{'message': {'content': json.dumps(expected)}}]}).encode()
        with patch('urllib.request.urlopen', return_value=Response()) as request:
            self.assertEqual(LLMPlanner().plan('테이블1 뒤로 1m 다시 2번', self.registry, default_attempts=4), expected)
        prompt = json.loads(request.call_args.args[0].data)['messages'][0]['content']
        self.assertIn('attempts=4', prompt)
        self.assertIn('원정', prompt)


if __name__ == '__main__':
    unittest.main()
