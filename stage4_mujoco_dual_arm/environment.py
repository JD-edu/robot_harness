from pathlib import Path

import mujoco
import numpy as np


class DualArmEnvironment:
    """Small MuJoCo scene used by all later educational stages."""

    def __init__(self, xml_path=None):
        path = Path(xml_path or Path(__file__).with_name("scene.xml"))
        self.model = mujoco.MjModel.from_xml_path(str(path))
        self.data = mujoco.MjData(self.model)
        self.held = {"left": None, "right": None}
        self.cap_open = False
        mujoco.mj_forward(self.model, self.data)

    def step(self, controls=None, steps=1):
        if controls is not None:
            values = np.asarray(controls, dtype=float)
            if values.shape != (self.model.nu,):
                raise ValueError("controls must contain {} actuator targets".format(self.model.nu))
            self.data.ctrl[:] = np.clip(values, self.model.actuator_ctrlrange[:, 0], self.model.actuator_ctrlrange[:, 1])
        for _ in range(steps):
            mujoco.mj_step(self.model, self.data)

    def joint_positions(self, arm):
        self._check_arm(arm)
        return np.array([self.data.joint(arm + "_shoulder").qpos[0], self.data.joint(arm + "_elbow").qpos[0]])

    def gripper_position(self, arm):
        self._check_arm(arm)
        return self.data.body(arm + "_gripper").xpos.copy()

    def object_position(self, name):
        if name not in ("pet", "cap", "cup"):
            raise KeyError("unknown object: " + name)
        return self.data.body(name).xpos.copy()

    def snapshot(self):
        joints = {}
        for index in range(self.model.njnt):
            name = self.model.joint(index).name
            joints[name] = float(self.data.joint(name).qpos[0])
        objects = {}
        for name in ("pet", "cap", "cup"):
            if mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name) >= 0:
                objects[name] = self.object_position(name).tolist()
        return {"joints": joints, "held": dict(self.held), "cap_open": self.cap_open, "objects": objects}

    @staticmethod
    def _check_arm(arm):
        if arm not in ("left", "right"):
            raise ValueError("arm must be left or right")
