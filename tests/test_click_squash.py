"""点击压扁动画与音效的回归测试。

对应契约 `契约-点击压扁动画与音效.md` 第 4 节的验收项：
  A1  短按松开          -> 压扁 + 播放 click
  A2  按住不动超过 10 帧 -> 不算点击，不压扁
  A3  拖拽后松手        -> 不压扁
  A4  动画期间再按      -> 被吞掉
  A5  动画期间          -> wandering 未启动
  A6  动画结束          -> 缩放精确复位为 1.0，wandering 启动
  A7  纵向压到 0.8、横向不变、底边为锚
  A8  连点              -> 每次都响、无残留变形
  A9  右键              -> 只开菜单，不压扁、不响 click
  B1  定时对话          -> 播放 talk
  B2  clickDialog       -> 不播放 talk
  B3  系统文字          -> 不播放 talk
  B4  音频文件缺失      -> 不崩，仅静音
  B5  `_initSound` 收录的路径是绝对的且文件真实存在
  A10 播放接口变慢      -> 动画仍必须跑满（QSoundEffect 曾阻塞 680 ms 把动画整个吃掉）

运行方式（在仓库根目录或 tests/ 下都可以）：
    python tests/test_click_squash.py

全部通过时退出码为 0，否则为 1。
"""
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# assets/ 与 config.json 都是相对路径，必须在导入程序和建 QApplication 之前切好
os.chdir(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

import SekibankiDesktopPet as app_module
from SekibankiDesktopPet import DesktopPet

FAIL = []


def check(label, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    if not ok:
        FAIL.append(label)


def pump(app, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.004)


def wait_until(app, cond, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.004)
    return cond()


def _send(widget, pos, kind, button):
    """kind: 'press' | 'release' | 'move'"""
    g = widget.mapToGlobal(pos)
    if kind == "press":
        ev = QMouseEvent(QEvent.MouseButtonPress, pos, g, button, button, Qt.NoModifier)
    elif kind == "release":
        ev = QMouseEvent(QEvent.MouseButtonRelease, pos, g, button, Qt.NoButton, Qt.NoModifier)
    else:
        ev = QMouseEvent(QEvent.MouseMove, pos, g, Qt.NoButton, button, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)


def press(widget, pos, button=Qt.LeftButton):
    _send(widget, pos, "press", button)


def release(widget, pos, button=Qt.LeftButton):
    _send(widget, pos, "release", button)


def move(widget, pos, button=Qt.LeftButton):
    _send(widget, pos, "move", button)


class PlayLog:
    """替身播放接口：只记录被播放了哪些音效，不真的出声，也不阻塞。"""

    def __init__(self):
        self.plays = []
        self.delay = 0.0

    def __call__(self, name):
        if self.delay:
            time.sleep(self.delay)
        self.plays.append(name)

    def count(self, name):
        return self.plays.count(name)

    def reset(self):
        self.plays = []


def sprite_size(pet):
    return int(pet.ORGINALWIDTH * pet._petImageSize), int(pet.ORGINALHEIGHT * pet._petImageSize)


def center(pet):
    return QPoint(pet.width() // 2, pet.height() // 2)


def click(pet):
    c = center(pet)
    press(pet, c)
    release(pet, c)


#-音频子系统-----------------------------------------------------------------------------------

def test_sound_assets_are_wired(pet):
    """B5：每个音效都指向真实存在、且是绝对路径的文件。"""
    check("B5 两个音效都收录了", set(pet._sfx.keys()) == {"click", "talk"},
          f"keys={sorted(pet._sfx.keys())}")
    for name, path in pet._sfx.items():
        check(f"B5 {name} 用绝对路径", os.path.isabs(path), path)
        check(f"B5 {name} 文件存在", os.path.isfile(path), f"exists={os.path.isfile(path)}")


def test_missing_sound_dir_is_survivable(app, pet):
    """B4：音频目录不存在时必须静音启动，而不是崩掉。"""
    good_dir = app_module.SOUND_DIR
    app_module.SOUND_DIR = os.path.join(REPO_ROOT, "assets", "Sound__does_not_exist")
    try:
        pet._initSound()
        check("B4 缺文件时不抛异常且不留音效", pet._sfx == {}, f"_sfx={pet._sfx}")
    except Exception as exc:                       # noqa: BLE001 - 这里就是要抓住任何异常
        check("B4 缺文件时不抛异常且不留音效", False, f"raised {exc!r}")
    finally:
        app_module.SOUND_DIR = good_dir
        pet._initSound()
    check("B4 恢复后音效重建成功", len(pet._sfx) == 2, f"keys={sorted(pet._sfx.keys())}")


#-压扁动画-------------------------------------------------------------------------------------

def test_short_click_squashes(app, pet, log):
    """A1 + A7 + A6：短按松开 -> 压扁到 0.8、横向不变、底边为锚、结束精确复位。"""
    W, H = sprite_size(pet)
    log.reset()

    click(pet)
    app.processEvents()

    check("A1 短按进入压扁状态", pet._busy is True, f"_busy={pet._busy}")
    check("A1 播放 click", log.count("click") == 1, f"plays={log.plays}")

    samples = []
    deadline = time.time() + 5.0
    while time.time() < deadline and pet._busy:
        app.processEvents()
        pm = pet.petLabel.pixmap()
        if pm is not None and not pm.isNull():
            #第四项：挤压期间标签上挂的必须是静态 pixmap，不是 GIF
            samples.append((pm.width(), pm.height(), pet.petLabel.pos().y(),
                            pet.petLabel.movie() is None))
        time.sleep(0.003)

    check("A7 采样到动画帧", len(samples) >= 5, f"n={len(samples)}")
    widths = {w for w, _h, _y, _m in samples}
    check("A7 横向尺寸始终不变", widths == {W}, f"widths={widths}")
    lowest = min(h for _w, h, _y, _m in samples)
    check("A7 纵向最低压到 0.8", abs(lowest - 0.8 * H) <= 0.02 * H,
          f"min={lowest} 期望≈{0.8 * H:.1f}")
    anchored = all(y == (H - h) // 2 for _w, h, y, _m in samples)
    check("A7 底边为锚（标签下移 H-h 的一半）", anchored,
          "全部样本满足 petLabel.y == (H-h)//2" if anchored else "有样本不满足")
    check("A11 挤压画的是静态拖拽图而非 GIF", all(m for *_r, m in samples),
          f"{sum(1 for *_r, m in samples if m)}/{len(samples)} 帧挂在 pixmap 上")

    check("A6 动画结束不再忙", pet._busy is False, f"_busy={pet._busy}")
    check("A6 结束后交还给站立 GIF", pet.petLabel.movie() is pet.petImage,
          f"movie is petImage: {pet.petLabel.movie() is pet.petImage}")
    final = pet.petImage.scaledSize()
    check("A6 缩放精确复位", (final.width(), final.height()) == (W, H),
          f"{final.width()}x{final.height()} 期望 {W}x{H}")
    check("A6 标签归位", pet.petLabel.pos().y() == 0, f"y={pet.petLabel.pos().y()}")


def test_slow_playback_does_not_eat_the_animation(app, pet, log):
    """A10：播放接口变慢时，动画仍必须完整播完。

    这是回归用例。此前用 QSoundEffect，play() 会阻塞 240-680 ms；由于启动动画的时钟在
    调 _playSound 之前就已经开始走，事件循环被冻住之后再没有定时器回调，第一个 tick 算出
    的 elapsed 已超过总时长，于是直接收尾 —— 声音响了、动画一帧都没有。
    """
    H = sprite_size(pet)[1]
    log.reset()
    log.delay = 0.3                                  # 模拟一个会阻塞 300 ms 的播放接口
    try:
        ticks = {"n": 0}
        orig_apply = pet._applySquash

        def counting(scale):
            ticks["n"] += 1
            orig_apply(scale)

        pet._applySquash = counting
        try:
            click(pet)
            deadline = time.time() + 5.0
            while pet._busy and time.time() < deadline:
                app.processEvents()
                time.sleep(0.003)
            app.processEvents()
        finally:
            pet._applySquash = orig_apply

        check("A10 播放阻塞时动画仍有多个帧", ticks["n"] >= 10, f"帧数={ticks['n']}")
        check("A10 播放阻塞后仍复位", pet._busy is False
              and pet.petImage.scaledSize().height() == H,
              f"_busy={pet._busy} 缩放={pet.petImage.scaledSize().height()}")
    finally:
        log.delay = 0.0


def test_hold_without_moving_is_not_a_click(app, pet, log):
    """A2：按住不动超过 10 帧就进入拖拽，松手不压扁。"""
    log.reset()

    press(pet, center(pet))
    pump(app, 0.3)                                  # > 125 ms，够数到第 10 帧
    # 合成事件下 QApplication.mouseButtons() 恒为 NoButton，_frame_has_passed 里的安全网
    # 会在 _draging 刚翻转的那一帧就把拖拽收掉，所以不能断言 _dragged 仍为 True。
    # 真正决定"这是拖拽而不是点击"的是按住时长跨过了第 10 帧阈值，查它才可靠。
    check("A2 按住跨过拖拽阈值", pet._frame_count >= 10, f"_frame_count={pet._frame_count}")
    release(pet, center(pet))
    app.processEvents()

    check("A2 松手不压扁", pet._busy is False, f"_busy={pet._busy}")
    check("A2 不播放 click", log.count("click") == 0, f"plays={log.plays}")


def test_drag_release_does_not_squash(app, pet, log):
    """A3：拖拽过的松手不压扁。

    合成事件驱动不了完整拖拽（_petDraggedMove 读的是真实光标坐标），所以这里直接把
    _draging/_dragged 置位，走 _endDrag 里 was_drag 为真的那条分支——压扁与否正是由它决定。
    """
    log.reset()

    press(pet, center(pet))
    pet._draging = True
    pet._dragged = True
    release(pet, center(pet))
    app.processEvents()

    check("A3 拖拽后不压扁", pet._busy is False, f"_busy={pet._busy}")
    check("A3 不播放 click", log.count("click") == 0, f"plays={log.plays}")
    check("A3 拖拽标志已清", pet._dragged is False and pet._draging is False,
          f"_dragged={pet._dragged} _draging={pet._draging}")


def test_press_during_squash_is_swallowed(app, pet, log):
    """A4：动画期间的一切鼠标事件都被吞掉，不排队也不补发。"""
    log.reset()

    click(pet)
    app.processEvents()
    check("A4 动画已开始", pet._busy is True, f"_busy={pet._busy}")

    press(pet, center(pet))                         # 动画期间按下
    app.processEvents()
    check("A4 期间按下不进入拖拽", pet._draging is False and pet._dragged is False,
          f"_draging={pet._draging} _dragged={pet._dragged}")
    check("A4 期间按下没有引发新动画", log.count("click") == 1, f"plays={log.plays}")

    release(pet, center(pet))                       # 动画期间松开
    app.processEvents()
    check("A4 期间松开同样被吞", log.count("click") == 1, f"plays={log.plays}")

    wait_until(app, lambda: not pet._busy, 3.0)
    check("A4 原动画仍正常收尾", pet._busy is False, f"_busy={pet._busy}")


def test_standby_held_until_squash_ends(app, pet, log):
    """A5 + A6：动画期间 wandering 不启动，结束后才启动。"""
    pet._wanderingTimer.stop()
    check("A5 前置：wandering 计时器已停", pet._wanderingTimer.isActive() is False,
          f"active={pet._wanderingTimer.isActive()}")

    click(pet)
    app.processEvents()
    check("A5 动画期间 wandering 未启动", pet._wanderingTimer.isActive() is False,
          f"active={pet._wanderingTimer.isActive()}")

    wait_until(app, lambda: not pet._busy, 3.0)
    check("A6 动画结束后 wandering 已启动", pet._wanderingTimer.isActive() is True,
          f"active={pet._wanderingTimer.isActive()}")


def test_repeated_clicks_all_fire(app, pet, log):
    """A8：每次点击都响、都压扁，且不留残留变形。"""
    W, H = sprite_size(pet)
    log.reset()

    for _ in range(5):
        click(pet)
        app.processEvents()
        wait_until(app, lambda: not pet._busy, 3.0)

    check("A8 五次点击响了五次", log.count("click") == 5, f"plays={log.plays}")
    final = pet.petImage.scaledSize()
    check("A8 无残留变形", (final.width(), final.height()) == (W, H) and pet.petLabel.pos().y() == 0,
          f"{final.width()}x{final.height()} y={pet.petLabel.pos().y()}")


def test_right_click_only_opens_menu(app, pet, log):
    """A9：右键只开设置菜单，不压扁、不响 click。"""
    log.reset()

    c = center(pet)
    press(pet, c, Qt.RightButton)
    release(pet, c, Qt.RightButton)
    app.processEvents()

    check("A9 右键不压扁", pet._busy is False, f"_busy={pet._busy}")
    check("A9 右键不播放 click", log.count("click") == 0, f"plays={log.plays}")

    pet._SettingMenuClose()
    pump(app, 0.05)


#-对话音效-------------------------------------------------------------------------------------

def _inject_dialog(pet, key):
    pet.DIALOGS[key] = {"id": key, "dialog": ["test"], "color": "white",
                        "textColor": "black", "time": 1, "start": 1, "end": 1}


def test_talk_plays_for_scheduled_dialog(app, pet, log):
    """B1：定时对话播放 talk。"""
    _inject_dialog(pet, "__squash_test__")
    log.reset()
    wait_until(app, lambda: pet._speechBubbleCondition is False, 3.0)

    pet._speechBubbling(id="__squash_test__")
    app.processEvents()

    check("B1 定时对话播放 talk", log.count("talk") == 1, f"plays={log.plays}")
    wait_until(app, lambda: pet._speechBubbleCondition is False, 5.0)


def test_click_dialog_does_not_play_talk(app, pet, log):
    """B2：点击对话不播放 talk（点击只响 click）。"""
    _inject_dialog(pet, "clickDialog")
    log.reset()
    pet._clickDialogExist = True
    wait_until(app, lambda: pet._speechBubbleCondition is False, 3.0)

    pet._triggerClickDialog()
    app.processEvents()

    check("B2 点击对话不播放 talk", log.count("talk") == 0, f"plays={log.plays}")
    wait_until(app, lambda: pet._speechBubbleCondition is False, 5.0)


def test_system_text_does_not_play_talk(app, pet, log):
    """B3：系统文字不是宠物在说话，不播放 talk。"""
    log.reset()
    wait_until(app, lambda: pet._speechBubbleCondition is False, 3.0)

    pet._speechBubbling("system text")
    app.processEvents()

    check("B3 系统文字不播放 talk", log.count("talk") == 0, f"plays={log.plays}")
    wait_until(app, lambda: pet._speechBubbleCondition is False, 5.0)


def main():
    app = QApplication(sys.argv)
    pet = DesktopPet()
    pet._wanderingTimer.stop()
    pet._wanderingTimer.setInterval(10 ** 7)
    pet._teleport()
    app.processEvents()

    # 真音效路径相关的两条先跑，之后 _playSound 会被替身换掉
    test_sound_assets_are_wired(pet)
    test_missing_sound_dir_is_survivable(app, pet)

    log = PlayLog()
    pet._playSound = log

    test_short_click_squashes(app, pet, log)
    test_slow_playback_does_not_eat_the_animation(app, pet, log)
    test_hold_without_moving_is_not_a_click(app, pet, log)
    test_drag_release_does_not_squash(app, pet, log)
    test_press_during_squash_is_swallowed(app, pet, log)
    test_standby_held_until_squash_ends(app, pet, log)
    test_repeated_clicks_all_fire(app, pet, log)
    test_right_click_only_opens_menu(app, pet, log)

    test_talk_plays_for_scheduled_dialog(app, pet, log)
    test_click_dialog_does_not_play_talk(app, pet, log)
    test_system_text_does_not_play_talk(app, pet, log)

    print()
    print(f"RESULT: {'ALL PASS' if not FAIL else 'FAILED -> ' + ', '.join(FAIL)}")

    pet.quit()
    app.processEvents()
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
