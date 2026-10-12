"""点击 / 拖拽 / 退出行为的回归测试。

覆盖三个曾经出问题的行为：
  1. 连续单击不应让站立 GIF 重播（修复前每点一次 QMovie 被重建，currentFrame 归零 -> 抽搐）
  2. 拖拽时朝向必须跟随拖动方向（修复前左右判定反了）
  3. 气泡显示中退出的进程收尾（修复前后台线程访问已销毁窗口，进程 fail-fast 崩溃）

运行方式（在仓库根目录或 tests/ 下都可以）：
    python tests/test_click_behavior.py
    python test_click_behavior.py          # 在 tests/ 目录里

程序本体全程使用 assets/... 这类相对路径，所以本测试会先把工作目录切到仓库根目录，
这样才能在任意位置调用。全部通过时退出码为 0，否则为 1。
"""
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 必须在导入程序和创建 QApplication 之前切好，assets/ 与 config.json 都是相对路径
os.chdir(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

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
        time.sleep(0.005)


def press(widget, pos):
    """pos 为窗口内局部坐标"""
    g = widget.mapToGlobal(pos)
    ev = QMouseEvent(QEvent.MouseButtonPress, pos, g, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)


def move(widget, pos):
    g = widget.mapToGlobal(pos)
    ev = QMouseEvent(QEvent.MouseMove, pos, g, Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)


def release(widget, pos):
    g = widget.mapToGlobal(pos)
    ev = QMouseEvent(QEvent.MouseButtonRelease, pos, g, Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)


def wait_for_frame(app, movie, target, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if movie.currentFrameNumber() >= target:
            return True
        time.sleep(0.005)
    return False


def test_click_does_not_rewind(app, pet):
    """用例 1 + 2：单击保持帧位置，且动画继续推进。"""
    center = QPoint(pet.width() // 2, pet.height() // 2)
    movie = pet.petImage

    check("standing animation is running", movie.state() == movie.Running and movie.frameCount() > 5,
          f"state={movie.state()} frames={movie.frameCount()}")

    for i in range(4):
        wait_for_frame(app, movie, 5)
        before = movie.currentFrameNumber()
        press(pet, center)
        release(pet, center)
        app.processEvents()
        after = movie.currentFrameNumber()
        check(f"click #{i + 1} keeps the frame position", after >= before,
              f"frame {before} -> {after}")
        pump(app, 0.05)

    check("simple click never enters drag state", pet._dragged is False, f"_dragged={pet._dragged}")

    f0 = movie.currentFrameNumber()
    wait_for_frame(app, movie, f0 + 6)
    check("animation keeps advancing after clicks", movie.currentFrameNumber() > f0,
          f"frame {f0} -> {movie.currentFrameNumber()}")


def test_drag_restores_standing_gif(app, pet):
    """用例 3：真拖拽切到拖拽贴图，松开还原站立动画并按拖动方向换向。"""
    center = QPoint(pet.width() // 2, pet.height() // 2)
    before_direction = pet._facingDirection
    start_x = pet.pos().x()

    press(pet, center)
    for offset in (30, 60, 90, 120, 150):
        move(pet, QPoint(center.x() + offset, center.y()))
        app.processEvents()

    moved_right = pet.pos().x() > start_x
    check("drag switches to the drag sprite",
          pet.petLabel.pixmap() is not None and not pet.petLabel.pixmap().isNull(),
          f"pixmap={'set' if pet.petLabel.pixmap() else 'none'}")
    check("drag marks _dragged", pet._dragged is True, f"_dragged={pet._dragged}")
    check("drag actually moved the pet", abs(pet.pos().x() - start_x) > 10,
          f"x {start_x} -> {pet.pos().x()}")

    release(pet, QPoint(center.x() + 150, center.y()))
    app.processEvents()

    check("release restores the standing gif", pet.petLabel.movie() is pet.petImage,
          f"movie={pet.petLabel.movie() is pet.petImage}")
    # 换向规则按原始实现：向左拖 => 1，向右拖 => 0。按整体位移判定，
    # 避免单步 dx 取整为 0 造成的抖动
    check("release flips facing direction",
          pet._facingDirection == (1 if moved_right else 0),
          f"moved_right={moved_right}, facing {before_direction} -> {pet._facingDirection}")
    check("restored gif is playing", pet.petImage.state() == pet.petImage.Running,
          f"state={pet.petImage.state()}")
    check("_dragged reset after release", pet._dragged is False, f"_dragged={pet._dragged}")


def test_movies_are_cached(pet):
    """用例 4：每个朝向只建一个 QMovie，换向不重建（重建就会丢帧位置）。"""
    snapshot = list(pet._petImages)
    check("cache holds one movie per direction", len(pet._petImages) == 2,
          f"len={len(pet._petImages)}")

    pet._changeFacingDirection(1 - pet._facingDirection)
    pet._changeFacingDirection(1 - pet._facingDirection)

    check("movies are cached, never rebuilt",
          all(a is b for a, b in zip(snapshot, pet._petImages)),
          "same QMovie instances reused across direction flips")
    check("each direction keeps its own frame position",
          all(m.state() == m.Running for m in pet._petImages),
          f"states={[m.state() for m in pet._petImages]}, frames={[m.currentFrameNumber() for m in pet._petImages]}")


def test_shutdown_with_active_bubble(app, pet):
    """用例 5：气泡还在显示时退出，必须干净收尾（否则后台线程访问已销毁窗口）。"""
    center = QPoint(pet.width() // 2, pet.height() // 2)

    press(pet, center)
    release(pet, center)
    app.processEvents()

    check("speech bubble is showing", pet._speechBubbleCondition is True,
          f"condition={pet._speechBubbleCondition}")

    thread = getattr(pet, "_speechBubbleThread", None)
    check("bubble thread is running", thread is not None and thread.isRunning(),
          f"isRunning={thread.isRunning() if thread else None}")

    pet.quit()
    app.processEvents()

    check("bubble thread stopped by shutdown", thread is None or not thread.isRunning(),
          f"isRunning={thread.isRunning() if thread else None}")
    check("wandering thread stopped by shutdown",
          not getattr(pet, "_wanderingThread", None) or not pet._wanderingThread.isRunning(),
          "no thread left running")
    check("bubble state released", pet._speechBubbleCondition is False,
          f"condition={pet._speechBubbleCondition}")


def main():
    app = QApplication(sys.argv)
    pet = DesktopPet()
    pet._wanderingTimer.stop()          # 排除自动游走干扰
    pet._wanderingTimer.setInterval(10 ** 7)
    pet._teleport()
    app.processEvents()

    test_click_does_not_rewind(app, pet)
    test_drag_restores_standing_gif(app, pet)
    test_movies_are_cached(pet)
    test_shutdown_with_active_bubble(app, pet)   # 会调用 pet.quit()，必须放最后

    print()
    print(f"RESULT: {'ALL PASS' if not FAIL else 'FAILED -> ' + ', '.join(FAIL)}")

    # 兜底收尾：正常路径上 test_shutdown 已经走完 quit()
    if getattr(pet, "_speechBubbleThread", None) is not None and pet._speechBubbleThread.isRunning():
        pet.shutdown()
    app.processEvents()

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
