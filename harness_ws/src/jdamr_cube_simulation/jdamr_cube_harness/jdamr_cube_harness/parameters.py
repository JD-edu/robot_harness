"""Explicit simulation adapters over the imported physical JDAMR parameters."""
from copy import deepcopy
from pathlib import Path
import yaml


def navigation_parameters(share, map_path, set_initial_pose=False, initial_pose=(0., 0., 0.)):
    share = Path(share)
    params = yaml.safe_load((share / 'config/upstream_new_base_nav2.yaml').read_text())
    params = deepcopy(params)

    def clocks(document):
        if not isinstance(document, dict):
            return
        for name, value in document.items():
            if name == 'ros__parameters':
                value['use_sim_time'] = True
                value['enable_stamped_cmd_vel'] = False
            else:
                clocks(value)
    clocks(params)
    amcl = params['amcl']['ros__parameters']
    amcl['set_initial_pose'] = set_initial_pose
    amcl['initial_pose'] = dict(zip(('x', 'y', 'yaw'), initial_pose), z=0.)
    params['map_server']['ros__parameters']['yaml_filename'] = str(map_path)
    params['bt_navigator']['ros__parameters']['default_nav_to_pose_bt_xml'] = str(
        share / 'behavior_trees/navigate_to_pose_staging_navfn_mppi.xml')
    controller = params['controller_server']['ros__parameters']
    controller['goal_checker_plugins'].append('staging_position_checker')
    controller['staging_position_checker'] = deepcopy(controller['position_goal_checker'])
    # The selected upstream staging variant uses NavFn + MPPI, not Lattice.
    params['planner_server']['ros__parameters']['planner_plugins'] = ['GridBased']
    monitor = params['collision_monitor']['ros__parameters']
    monitor['cmd_vel_in_topic'] = '/jdamr_harness/selected_cmd_vel'
    monitor['cmd_vel_out_topic'] = '/cmd_vel'
    return params
