"""Reuse the validated Qwen3 planner and mission engine with JDAMR locations."""
import sys
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from SLAM_harness_jazzy.main import main as harness_main


def main(args=None):
    argv = list(sys.argv[1:] if args is None else args)
    split = argv.index('--ros-args') if '--ros-args' in argv else len(argv)
    if not any(arg == '--locations' or arg.startswith('--locations=') for arg in argv[:split]):
        path = Path(get_package_share_directory('jdamr_cube_harness')) / 'config/locations.yaml'
        argv[split:split] = ['--locations', str(path)]
    # JDAMR's upstream staging checker judges position, leaving heading to fine control.
    # Allow the low-speed turn plus approach to complete; retain explicit user limits.
    if not any(arg == '--align-timeout' or arg.startswith('--align-timeout=') for arg in argv[:split]):
        split = argv.index('--ros-args') if '--ros-args' in argv else len(argv)
        argv[split:split] = ['--align-timeout', '60']
    return harness_main(argv)
