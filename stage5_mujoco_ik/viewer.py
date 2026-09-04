"""Stage 5 전용 GLFW 기반 MuJoCo renderer."""

from __future__ import annotations

import glfw
import mujoco


class GLFWRenderer:
    """mujoco.viewer 없이 GLFW window와 MjrContext를 직접 관리한다."""

    def __init__(self, env, width=1000, height=700, title="Stage 5 - JDCobot200 IK"):
        self.env = env
        if not glfw.init():
            raise RuntimeError("GLFW 초기화 실패: DISPLAY 또는 OpenGL 설정을 확인하세요.")

        self.window = None
        self.context = None
        try:
            glfw.window_hint(glfw.SAMPLES, 4)
            self.window = glfw.create_window(width, height, title, None, None)
            if self.window is None:
                raise RuntimeError("GLFW window를 만들 수 없습니다.")
            glfw.make_context_current(self.window)
            glfw.swap_interval(1)

            self.camera = mujoco.MjvCamera()
            self.option = mujoco.MjvOption()
            self.scene = mujoco.MjvScene(env.model, maxgeom=2000)
            self.context = mujoco.MjrContext(
                env.model, mujoco.mjtFontScale.mjFONTSCALE_150.value
            )
            self.camera.lookat[:] = env.gripper_position()
            self.camera.distance = 0.8
            self.camera.azimuth = 135
            self.camera.elevation = -25
            self._mouse = {"left": False, "middle": False, "right": False, "x": 0.0, "y": 0.0}
            self._install_callbacks()
        except Exception:
            self.close()
            raise

    def _install_callbacks(self):
        def key_callback(window, key, _scancode, action, _mods):
            if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
                glfw.set_window_should_close(window, True)

        def button_callback(window, _button, _action, _mods):
            self._mouse["left"] = glfw.get_mouse_button(window, glfw.MOUSE_BUTTON_LEFT) == glfw.PRESS
            self._mouse["middle"] = glfw.get_mouse_button(window, glfw.MOUSE_BUTTON_MIDDLE) == glfw.PRESS
            self._mouse["right"] = glfw.get_mouse_button(window, glfw.MOUSE_BUTTON_RIGHT) == glfw.PRESS
            self._mouse["x"], self._mouse["y"] = glfw.get_cursor_pos(window)

        def cursor_callback(window, x, y):
            dx, dy = x - self._mouse["x"], y - self._mouse["y"]
            self._mouse["x"], self._mouse["y"] = x, y
            if not (self._mouse["left"] or self._mouse["middle"] or self._mouse["right"]):
                return
            _, height = glfw.get_window_size(window)
            shift = glfw.get_key(window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS
            shift = shift or glfw.get_key(window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS
            if self._mouse["right"]:
                action = mujoco.mjtMouse.mjMOUSE_MOVE_H if shift else mujoco.mjtMouse.mjMOUSE_MOVE_V
            elif self._mouse["left"]:
                action = mujoco.mjtMouse.mjMOUSE_ROTATE_H if shift else mujoco.mjtMouse.mjMOUSE_ROTATE_V
            else:
                action = mujoco.mjtMouse.mjMOUSE_ZOOM
            mujoco.mjv_moveCamera(
                self.env.model, action, dx / max(height, 1), dy / max(height, 1), self.scene, self.camera
            )

        def scroll_callback(_window, _x_offset, y_offset):
            mujoco.mjv_moveCamera(
                self.env.model, mujoco.mjtMouse.mjMOUSE_ZOOM,
                0.0, -0.05 * y_offset, self.scene, self.camera
            )

        glfw.set_key_callback(self.window, key_callback)
        glfw.set_mouse_button_callback(self.window, button_callback)
        glfw.set_cursor_pos_callback(self.window, cursor_callback)
        glfw.set_scroll_callback(self.window, scroll_callback)

    def is_running(self):
        return self.window is not None and not glfw.window_should_close(self.window)

    def render(self):
        if not self.is_running():
            return
        glfw.make_context_current(self.window)
        width, height = glfw.get_framebuffer_size(self.window)
        viewport = mujoco.MjrRect(0, 0, width, height)
        mujoco.mjv_updateScene(
            self.env.model, self.env.data, self.option, None, self.camera,
            mujoco.mjtCatBit.mjCAT_ALL.value, self.scene,
        )
        mujoco.mjr_render(viewport, self.scene, self.context)
        glfw.swap_buffers(self.window)
        glfw.poll_events()

    def close(self):
        if self.context is not None:
            self.context.free()
            self.context = None
        if self.window is not None:
            glfw.destroy_window(self.window)
            self.window = None
        glfw.terminate()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()
