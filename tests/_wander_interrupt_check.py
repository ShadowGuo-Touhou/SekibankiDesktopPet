"""一次性核对：闲逛被拖拽打断（临时脚本，跑完可删）。

跑法（项目根目录）：python tests/_wander_interrupt_check.py
"""
import sys
import time

sys.path.insert(0, ".")
from PyQt5.QtCore import Qt, QEvent, QPoint          # noqa: E402
from PyQt5.QtGui import QMouseEvent                  # noqa: E402
from PyQt5.QtWidgets import QApplication             # noqa: E402

import SekibankiDesktopPet as M                      # noqa: E402

FAIL = []


def check(label, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    if not ok:
        FAIL.append(label)


def pump(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.004)


def press(widget, pos, button=Qt.LeftButton):
    g = widget.mapToGlobal(pos)
    QApplication.sendEvent(widget, QMouseEvent(
        QEvent.MouseButtonPress, pos, g, button, button, Qt.NoModifier))


def release(widget, pos, button=Qt.LeftButton):
    g = widget.mapToGlobal(pos)
    QApplication.sendEvent(widget, QMouseEvent(
        QEvent.MouseButtonRelease, pos, g, button, Qt.NoButton, Qt.NoModifier))


def thread_running(pet):
    try:
        return pet._wanderingThread.isRunning()
    except RuntimeError:              # 已被 deleteLater 回收
        return False


app = QApplication(sys.argv)
pet = M.DesktopPet()
pet.show()
pump(app, 0.1)

center = QPoint(pet.width() // 2, pet.height() // 2)
pet._wanderingTimer.stop()            # 手动控制，别让真计时器插进来

# ---- 1 · 必须真的有一个「在飞」的闲逛，否则打断无从谈起 ----
# 闲逛的目的地是随机的，算出来的位移有时很短（甚至为 0），那种闲逛几十毫秒就跑完，
# 采样窗口里啥也看不到。所以重试到一个确实在跑、且窗口确实在动的闲逛为止。
moving = False
detail = ""
for attempt in range(12):
    pet._wandering()
    pump(app, 0.07)
    if not thread_running(pet):
        continue
    seen = set()
    for _ in range(10):
        seen.add((pet.pos().x(), pet.pos().y()))
        pump(app, 0.03)
    span = max(p[0] for p in seen) - min(p[0] for p in seen) \
        + max(p[1] for p in seen) - min(p[1] for p in seen)
    if len(seen) > 2 and thread_running(pet):
        moving = True
        detail = f"第 {attempt + 1} 次尝试：采到 {len(seen)} 个位置，总位移 {span}px，线程 running=True"
        break
    # 这次闲逛太短了，等它自己收场再重试
    while thread_running(pet):
        pump(app, 0.02)
    detail = f"第 {attempt + 1} 次尝试太平淡（{len(seen)} 个位置），重试"
check("存在正在移动的闲逛", moving, detail)

# ---- 2 · 按下立即打断 ----
press(pet, center)
work = pet._wanderingWork
check("worker 收到停止请求", getattr(work, "_stopRequested", None) is True,
      f"_stopRequested={getattr(work, '_stopRequested', None)}")
pump(app, 0.06)
check("闲逛线程已退出", not thread_running(pet),
      f"isRunning={thread_running(pet)}")

# ---- 3 · 按住期间不能被重新武装（这是第二个洞） ----
pet._wanderingTimer.stop()
pet._wanderIngTimerReset()
check("按住时 _wanderIngTimerReset 不武装", not pet._wanderingTimer.isActive(),
      f"isActive={pet._wanderingTimer.isActive()}")

held_thread = pet._wanderingThread
pet._wandering()
check("按住时 _wandering 不新建 worker", pet._wanderingThread is held_thread,
      "线程对象未变，没有新的闲逛被启动")

# ---- 4 · 按住期间窗口不再被闲逛搬动 ----
# 停掉按下计时器，把「拖拽自己会移动窗口」这条路径隔离掉，
# 这样位置变化就只可能来自闲逛。
pet._pressTimer.stop()
before = (pet.pos().x(), pet.pos().y())
pump(app, 0.3)
after = (pet.pos().x(), pet.pos().y())
check("按住后闲逛不再移动窗口", before == after, f"{before} -> {after}")

# ---- 5 · 松手后闲逛恢复 ----
release(pet, center)
pump(app, 0.1)
pet._wanderIngTimerReset()
check("松手后 _wanderIngTimerReset 正常武装", pet._wanderingTimer.isActive(),
      f"isActive={pet._wanderingTimer.isActive()}")

pet.shutdown()
print()
print("FAILED:", FAIL if FAIL else "none")
sys.exit(1 if FAIL else 0)
