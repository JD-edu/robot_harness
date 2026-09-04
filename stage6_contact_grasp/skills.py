"""Stage 6에서 Harness가 호출하는 공통 Skill 계약과 MuJoCo 구현."""

import numpy as np

from stage5_mujoco_ik.ik import IKSolver


class RobotSkill:
    name = ""
    description = ""
    parameters = {}

    def schema(self):
        return {"name": self.name, "description": self.description,
                "parameters": self.parameters.copy()}

    def validate_args(self, args):
        if not isinstance(args, dict) or set(args) != set(self.parameters):
            names = ", ".join(self.parameters)
            raise ValueError(f"{self.name} args must be exactly: {names}")


class MoveToSkill(RobotSkill):
    """숫자 xyz를 실행하는 저수준 Skill. 계획에는 직접 노출하지 않는다."""

    name = "move_to"
    description = "Move the TCP to an absolute xyz position with IK."
    parameters = {"x": "number", "y": "number", "z": "number"}

    def __init__(self, env, step_callback=None):
        self.env = env
        self.ik = IKSolver(env)
        self.step_callback = step_callback

    def validate_args(self, args):
        super().validate_args(args)
        if not all(isinstance(args[key], (int, float)) for key in self.parameters):
            raise ValueError("x, y, z must be numbers")

    def execute(self, args):
        self.validate_args(args)
        return self.ik.move_to([args["x"], args["y"], args["z"]],
                               step_callback=self.step_callback)


class MoveToObjectSkill(RobotSkill):
    """객체 이름을 MuJoCo 위치로 변환한 뒤 MoveToSkill을 호출한다."""

    name = "move_to_object"
    description = "Move the TCP to a named object's current MuJoCo position."
    parameters = {"object": "known object name"}

    def __init__(self, env, move_to):
        self.env = env
        self.move_to = move_to

    def validate_args(self, args):
        super().validate_args(args)
        if args["object"] != "red_block":
            raise ValueError("unknown object: " + str(args["object"]))

    def execute(self, args):
        self.validate_args(args)
        position = self.env.body_position(args["object"])
        xyz = dict(zip(("x", "y", "z"), position.tolist()))
        result = self.move_to.execute(xyz)
        result["resolved_object"] = args["object"]
        result["resolved_xyz"] = position.copy()
        return result


class GraspSkill(RobotSkill):
    """그리퍼를 닫고 실제 MuJoCo contact가 생긴 경우에만 weld로 결합한다."""

    name = "grasp"
    description = "Close the gripper and attach a contacted named object."
    parameters = {"object": "known object name"}

    def __init__(self, env, close_steps=200):
        self.env = env
        self.close_steps = int(close_steps)
        self.held_object = None

    def validate_args(self, args):
        super().validate_args(args)
        if args["object"] != "red_block":
            raise ValueError("unknown object: " + str(args["object"]))

    def execute(self, args):
        self.validate_args(args)
        if self.held_object is not None:
            return {"ok": False, "code": "HAND_NOT_EMPTY"}
        self.env.set_grasp_collisions(True)
        self.env.command_gripper(True)
        contact_count = 0
        for _ in range(self.close_steps):
            self.env.step()
            contact_count = (
                self.env.contacts_between("left_grasp_pad", "red_block_geom")
                + self.env.contacts_between("right_grasp_pad", "red_block_geom")
            )
            if contact_count:
                self.env.attach_red_block()
                self.held_object = args["object"]
                return {"ok": True, "code": "GRASP_SUCCESS",
                        "object": self.held_object, "contacts": contact_count,
                        "physically_attached": True}
        distance = float(np.linalg.norm(
            self.env.gripper_position() - self.env.body_position(args["object"])))
        return {"ok": False, "code": "GRASP_NO_CONTACT", "distance": distance}


class LiftSkill(RobotSkill):
    name = "lift"
    description = "Lift the currently grasped object by a bounded distance."
    parameters = {"dz": "number from 0.01 to 0.10 metres"}

    def __init__(self, env, move_to, grasp):
        self.env = env
        self.move_to = move_to
        self.grasp = grasp

    def validate_args(self, args):
        super().validate_args(args)
        if not isinstance(args["dz"], (int, float)) or not 0.01 <= args["dz"] <= 0.10:
            raise ValueError("dz must be between 0.01 and 0.10")

    def execute(self, args):
        self.validate_args(args)
        if self.grasp.held_object is None:
            return {"ok": False, "code": "HAND_EMPTY"}
        target = self.env.gripper_position() + [0.0, 0.0, args["dz"]]
        return self.move_to.execute(dict(zip(("x", "y", "z"), target.tolist())))
