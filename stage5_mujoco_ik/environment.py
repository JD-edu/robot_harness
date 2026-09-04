"""Stage 5 전용 JDCobot200 MuJoCo 환경."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import mujoco
import numpy as np


class JDCobot200Environment:
    """jdcobot200.xml을 로드하고 관절 위치 제어를 제공한다."""

    ARM_JOINT_NAMES = ("base", "shoulder", "elbow", "wrist_pitch", "wrist_roll")
    END_EFFECTOR_SITE = "graspframe"

    def __init__(self, xml_path: str | Path | None = None) -> None:
        path = Path(xml_path) if xml_path is not None else Path(__file__).with_name("scene.xml")
        self.model = mujoco.MjModel.from_xml_path(str(path.resolve()))
        self.data = mujoco.MjData(self.model)
        self.arm_actuator_ids = np.array(
            [self._require_id(mujoco.mjtObj.mjOBJ_ACTUATOR, name) for name in self.ARM_JOINT_NAMES], dtype=int
        )
        self.arm_joint_ids = np.array(
            [self._require_id(mujoco.mjtObj.mjOBJ_JOINT, name) for name in self.ARM_JOINT_NAMES], dtype=int
        )
        self.arm_qpos_addresses = self.model.jnt_qposadr[self.arm_joint_ids]
        self.site_id = self._require_id(mujoco.mjtObj.mjOBJ_SITE, self.END_EFFECTOR_SITE)
        self.target_body_id = self._require_id(mujoco.mjtObj.mjOBJ_BODY, "ik_target")
        self.target_mocap_id = int(self.model.body_mocapid[self.target_body_id])
        self.gripper_actuator_ids = np.array([
            self._require_id(mujoco.mjtObj.mjOBJ_ACTUATOR, "stage6_left_gripper"),
            self._require_id(mujoco.mjtObj.mjOBJ_ACTUATOR, "stage6_right_gripper"),
        ], dtype=int)
        self.grasp_equality_id = self._require_id(mujoco.mjtObj.mjOBJ_EQUALITY, "red_block_grasp")
        self.gripper_body_id = self._require_id(mujoco.mjtObj.mjOBJ_BODY, "gripper_assembly")
        self.red_block_body_id = self._require_id(mujoco.mjtObj.mjOBJ_BODY, "red_block")
        self.grasp_pad_geom_ids = np.array([
            self._require_id(mujoco.mjtObj.mjOBJ_GEOM, "left_grasp_pad"),
            self._require_id(mujoco.mjtObj.mjOBJ_GEOM, "right_grasp_pad"),
        ], dtype=int)
        self.reset()

    def _require_id(self, object_type: mujoco.mjtObj, name: str) -> int:
        object_id = mujoco.mj_name2id(self.model, object_type, name)
        if object_id < 0:
            raise ValueError(f"MuJoCo model에 {name!r}이(가) 없습니다.")
        return int(object_id)

    @property
    def timestep(self) -> float:
        return float(self.model.opt.timestep)

    def reset(self, arm_qpos: Iterable[float] | None = None) -> np.ndarray:
        mujoco.mj_resetData(self.model, self.data)
        if arm_qpos is not None:
            self.data.qpos[self.arm_qpos_addresses] = self._validate_arm_values(arm_qpos)
        self.data.ctrl[self.arm_actuator_ids] = self.arm_positions()
        self.data.ctrl[self.gripper_actuator_ids] = 0.0
        self.data.eq_active[self.grasp_equality_id] = 0
        self.set_grasp_collisions(False)
        mujoco.mj_forward(self.model, self.data)
        return self.arm_positions()

    def _validate_arm_values(self, values: Iterable[float]) -> np.ndarray:
        array = np.asarray(values, dtype=float)
        expected = (len(self.ARM_JOINT_NAMES),)
        if array.shape != expected or not np.all(np.isfinite(array)):
            raise ValueError(f"arm 관절값은 유한한 값 {expected} shape이어야 합니다.")
        return array

    def arm_positions(self) -> np.ndarray:
        return self.data.qpos[self.arm_qpos_addresses].copy()

    def gripper_position(self) -> np.ndarray:
        return self.data.site_xpos[self.site_id].copy()

    def command_arm(self, arm_qpos: Iterable[float]) -> np.ndarray:
        values = self._validate_arm_values(arm_qpos)
        ranges = self.model.actuator_ctrlrange[self.arm_actuator_ids]
        command = np.clip(values, ranges[:, 0], ranges[:, 1])
        self.data.ctrl[self.arm_actuator_ids] = command
        return command.copy()

    def set_target_marker(self, xyz: Iterable[float]) -> None:
        target = np.asarray(xyz, dtype=float)
        if target.shape != (3,) or not np.all(np.isfinite(target)):
            raise ValueError("target marker는 유한한 xyz 값 3개여야 합니다.")
        self.data.mocap_pos[self.target_mocap_id] = target
        mujoco.mj_forward(self.model, self.data)

    def body_position(self, name: str) -> np.ndarray:
        body_id = self._require_id(mujoco.mjtObj.mjOBJ_BODY, name)
        return self.data.xpos[body_id].copy()

    def command_gripper(self, closed: bool) -> None:
        # 두 finger joint가 서로 반대 방향으로 회전한다.
        command = np.array([-0.012, 0.012]) if closed else np.array([0.0, 0.0])
        self.data.ctrl[self.gripper_actuator_ids] = command

    def set_grasp_collisions(self, enabled: bool) -> None:
        value = 1 if enabled else 0
        self.model.geom_contype[self.grasp_pad_geom_ids] = value
        self.model.geom_conaffinity[self.grasp_pad_geom_ids] = value

    def contacts_between(self, geom_name: str, other_geom_name: str) -> int:
        first = self._require_id(mujoco.mjtObj.mjOBJ_GEOM, geom_name)
        second = self._require_id(mujoco.mjtObj.mjOBJ_GEOM, other_geom_name)
        count = 0
        for contact in self.data.contact:
            if {int(contact.geom1), int(contact.geom2)} == {first, second}:
                count += 1
        return count

    def attach_red_block(self) -> None:
        # XML이 기억하는 초기 상대 자세로 weld하면 블록이 순간이동한다. 접촉 순간의
        # body2(red_block) pose를 body1(gripper) 좌표계로 변환해 weld relpose에 기록한다.
        gripper_rotation = self.data.xmat[self.gripper_body_id].reshape(3, 3)
        relative_position = gripper_rotation.T @ (
            self.data.xpos[self.red_block_body_id] - self.data.xpos[self.gripper_body_id]
        )
        inverse_gripper_quat = np.empty(4, dtype=float)
        relative_quat = np.empty(4, dtype=float)
        mujoco.mju_negQuat(inverse_gripper_quat, self.data.xquat[self.gripper_body_id])
        mujoco.mju_mulQuat(
            relative_quat,
            inverse_gripper_quat,
            self.data.xquat[self.red_block_body_id],
        )
        self.model.eq_data[self.grasp_equality_id, 3:6] = relative_position
        self.model.eq_data[self.grasp_equality_id, 6:10] = relative_quat
        self.data.eq_active[self.grasp_equality_id] = 1
        mujoco.mj_forward(self.model, self.data)

    def step(self, steps: int = 1) -> None:
        if steps < 1:
            raise ValueError("steps는 1 이상이어야 합니다.")
        for _ in range(steps):
            mujoco.mj_step(self.model, self.data)

    def observation(self) -> dict[str, object]:
        return {
            "time": float(self.data.time),
            "arm_qpos": self.arm_positions().tolist(),
            "gripper_position": self.gripper_position().tolist(),
        }
