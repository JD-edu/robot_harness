"""Simulation distance override; imported physical profiles remain unchanged."""
import math

DEFAULT_SLAM_MAX_RANGE = 8.0
SENSOR_MAX_RANGE = 16.0


def mapping_configuration(source, max_range=DEFAULT_SLAM_MAX_RANGE):
    distance = float(max_range)
    if not math.isfinite(distance) or not 0.28 < distance <= SENSOR_MAX_RANGE:
        raise ValueError('slam_max_range must be finite, greater than 0.28 and at most 16.0 metres')
    body, separator, tail = source.rpartition('return options')
    if not separator or tail.strip():
        raise ValueError('Expected a Cartographer profile ending with return options')
    return (body + '\n-- Gazebo-only range override; physical source is preserved.\n'
            + f'TRAJECTORY_BUILDER_2D.max_range = {distance!r}\n'
            + 'return options\n')
