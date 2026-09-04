import argparse
import time

import glfw
import mujoco

try:
    from stage4_mujoco_dual_arm.environment import DualArmEnvironment
except ModuleNotFoundError:
    from environment import DualArmEnvironment


DEFAULT_CONTROLS = [0.0, 0.2, -0.3, 0.0, 0.0, 0.0]


def run_glfw(env, duration=0.0):
    """Render MuJoCo directly in a GLFW window."""

    if not glfw.init():
        raise RuntimeError("GLFW 초기화 실패: DISPLAY 또는 OpenGL 설정을 확인하세요")

    window = None
    context = None
    try:
        glfw.window_hint(glfw.SAMPLES, 4)
        window = glfw.create_window(1000, 700, "Stage 4 - Dual Arm MuJoCo", None, None)
        if window is None:
            raise RuntimeError("GLFW 창을 만들 수 없습니다")
        glfw.make_context_current(window)
        glfw.swap_interval(1)

        camera = mujoco.MjvCamera()
        option = mujoco.MjvOption()
        scene = mujoco.MjvScene(env.model, maxgeom=2000)
        context = mujoco.MjrContext(env.model, mujoco.mjtFontScale.mjFONTSCALE_150.value)
        camera.lookat[:] = [0.0, 0.0, 0.15]
        camera.distance = 1.7
        camera.azimuth = 90
        camera.elevation = -35

        mouse = {"left": False, "middle": False, "right": False, "x": 0.0, "y": 0.0}

        def key_callback(_window, key, _scancode, action, _mods):
            if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
                glfw.set_window_should_close(_window, True)

        def button_callback(_window, _button, _action, _mods):
            mouse["left"] = glfw.get_mouse_button(_window, glfw.MOUSE_BUTTON_LEFT) == glfw.PRESS
            mouse["middle"] = glfw.get_mouse_button(_window, glfw.MOUSE_BUTTON_MIDDLE) == glfw.PRESS
            mouse["right"] = glfw.get_mouse_button(_window, glfw.MOUSE_BUTTON_RIGHT) == glfw.PRESS
            mouse["x"], mouse["y"] = glfw.get_cursor_pos(_window)

        def cursor_callback(_window, x, y):
            dx, dy = x - mouse["x"], y - mouse["y"]
            mouse["x"], mouse["y"] = x, y
            if not (mouse["left"] or mouse["middle"] or mouse["right"]):
                return
            width, height = glfw.get_window_size(_window)
            shift = glfw.get_key(_window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS
            shift = shift or glfw.get_key(_window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS
            if mouse["right"]:
                action = mujoco.mjtMouse.mjMOUSE_MOVE_H if shift else mujoco.mjtMouse.mjMOUSE_MOVE_V
            elif mouse["left"]:
                action = mujoco.mjtMouse.mjMOUSE_ROTATE_H if shift else mujoco.mjtMouse.mjMOUSE_ROTATE_V
            else:
                action = mujoco.mjtMouse.mjMOUSE_ZOOM
            mujoco.mjv_moveCamera(env.model, action, dx / max(height, 1), dy / max(height, 1), scene, camera)

        def scroll_callback(_window, _x_offset, y_offset):
            mujoco.mjv_moveCamera(env.model, mujoco.mjtMouse.mjMOUSE_ZOOM, 0.0, -0.05 * y_offset, scene, camera)

        glfw.set_key_callback(window, key_callback)
        glfw.set_mouse_button_callback(window, button_callback)
        glfw.set_cursor_pos_callback(window, cursor_callback)
        glfw.set_scroll_callback(window, scroll_callback)

        start = time.monotonic()
        while not glfw.window_should_close(window):
            frame_start = time.monotonic()
            env.step(DEFAULT_CONTROLS)
            width, height = glfw.get_framebuffer_size(window)
            viewport = mujoco.MjrRect(0, 0, width, height)
            mujoco.mjv_updateScene(
                env.model,
                env.data,
                option,
                None,
                camera,
                mujoco.mjtCatBit.mjCAT_ALL.value,
                scene,
            )
            mujoco.mjr_render(viewport, scene, context)
            glfw.swap_buffers(window)
            glfw.poll_events()

            if duration > 0 and time.monotonic() - start >= duration:
                break
            remaining = env.model.opt.timestep - (time.monotonic() - frame_start)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        if context is not None:
            context.free()
        if window is not None:
            glfw.destroy_window(window)
        glfw.terminate()


def main():
    parser = argparse.ArgumentParser(description="Stage 4 dual-arm MuJoCo scene")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="do not open a window; run 20 simulation steps and print state",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="viewer runtime in seconds; 0 means until the window is closed",
    )
    args = parser.parse_args()

    env = DualArmEnvironment()
    if args.headless:
        env.step(DEFAULT_CONTROLS, 20)
        print("STAGE 4 READY (headless):", env.snapshot())
        return

    print("Stage 4 GLFW 렌더러를 시작합니다. ESC 또는 창 닫기로 종료합니다.")
    try:
        run_glfw(env, duration=args.duration)
    except (RuntimeError, mujoco.FatalError) as error:
        raise SystemExit(
            "GLFW 렌더링 창을 열 수 없습니다: {}\n"
            "GUI 세션에서 실행하거나 --headless 옵션을 사용하세요.".format(error)
        )
    print("STAGE 4 FINISHED:", env.snapshot())


if __name__ == "__main__":
    main()
