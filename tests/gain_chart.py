"""把 amplifier 对摆动幅度的影响画成对照图（离屏渲染，不弹窗）。

配套 `sim_pendulum.py --gain`（那个是纯数字）。这里出图，用来一眼确认：
三个 amp 下 θ 曲线的**过零点完全对齐**（周期不变），只是幅度在长。

跑法：python tests/gain_chart.py
输出：tests/gain_curves.png
"""
import math
import sys

sys.path.insert(0, "tests")
import sim_pendulum as S                                    # noqa: E402

from PyQt5.QtCore import Qt, QPointF                        # noqa: E402
from PyQt5.QtGui import (QGuiApplication, QImage, QPainter,  # noqa: E402
                         QColor, QFont, QPen, QPolygonF)

app = QGuiApplication(sys.argv)

grab_angle, r = S.grab_geometry(S.SPRITE, S.SPRITE, S.GRAB_LOCAL)
theta0 = -math.radians(grab_angle)
preset_name, ka, kv, tau_a, zeta = S.PRESETS[2]      # C 速度扶正 = 项目实机那套 SWING_*
path = S.build_demo_path(S.DT)

AMPS = (1.0, 2.0, 3.0)
COLORS = (QColor(45, 120, 230), QColor(240, 140, 30), QColor(210, 55, 80))

runs = [S.simulate(path, r, S.DEFAULT_G, zeta, theta0, True,
                   kv=kv, ka=ka, tau_a=tau_a, amp=a) for a in AMPS]

W, H = 1080, 660
L, RT, TP, B = 84, 1030, 96, 560
TSPAN = len(path) * S.DT
YMAX = 130.0

WIN_T0, WIN_T1 = 0.6, 2.6            # 匀速拖动窗口


def X(t):
    return L + (RT - L) * t / TSPAN


def Y(th):
    return B - (B - TP) * (th + YMAX) / (2 * YMAX)


img = QImage(W, H, QImage.Format_ARGB32)
img.fill(QColor(250, 250, 248))
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)

# 匀速拖动窗口
p.fillRect(int(X(WIN_T0)), TP, int(X(WIN_T1) - X(WIN_T0)), B - TP,
           QColor(234, 240, 250))

# 过零辅助线：取 amp=1 的过零时刻，三条曲线应当同时穿过
crossings, prev = [], None
for row in runs[0]:
    th = row["theta_deg"]
    if prev is not None and prev * th < 0.0:
        crossings.append(row["t"])
    prev = th
for t in crossings:
    p.setPen(QPen(QColor(190, 100, 190, 130), 1, Qt.DashLine))
    p.drawLine(int(X(t)), TP, int(X(t)), B)

# 网格与刻度
p.setFont(QFont("Consolas", 10))
for th in range(-120, 121, 30):
    y = int(Y(th))
    p.setPen(QPen(QColor(150, 150, 150) if th == 0 else QColor(228, 228, 228), 1))
    p.drawLine(L, y, RT, y)
    p.setPen(QColor(105, 105, 105))
    p.drawText(L - 54, y + 4, f"{th:4d}°")
for t in range(0, int(TSPAN) + 1):
    x = int(X(t))
    p.setPen(QPen(QColor(228, 228, 228), 1))
    p.drawLine(x, TP, x, B)
    p.setPen(QColor(105, 105, 105))
    p.drawText(x - 8, B + 20, f"{t}s")

# θ 曲线
for rows, col in zip(runs, COLORS):
    p.setPen(QPen(col, 2.0))
    p.drawPolyline(QPolygonF([QPointF(X(rw["t"]), Y(rw["theta_deg"]))
                              for rw in rows]))

# 标题
p.setPen(QColor(25, 25, 25))
p.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
p.drawText(L, 36, "amplifier 只放大摆动幅度，不改变摆动周期")
p.setFont(QFont("Consolas", 9))
p.setPen(QColor(95, 95, 95))
p.drawText(L, 58, f"同一段鼠标轨迹 · {preset_name}  ka {ka} kv {kv} zeta {zeta}"
                  f" · theta 里已含 amp，渲染角 = grabAngle + theta")
p.setPen(QColor(160, 100, 180))
p.drawText(L, 78, "紫色虚线 = amp=1 的过零时刻：三条曲线同时穿过 → 周期与 amp 无关")

# 右上读数：固定列宽的表格，避免行间互相压字
p.setFont(QFont("Consolas", 10))
p.setPen(QColor(85, 85, 85))
p.drawText(660, 128, "amp")
p.drawText(745, 128, "匀速倾斜")
p.drawText(845, 128, "max|θ|")
p.drawText(935, 128, "自由周期")
for i, (rows, a, col) in enumerate(zip(runs, AMPS, COLORS)):
    peak = max(abs(rw["theta_deg"]) for rw in rows)
    per = S._decay_period(rows, 3.3)
    tilt = sum(rw["theta_deg"] for rw in rows
               if WIN_T1 - 0.7 <= rw["t"] < WIN_T1) / (0.7 * S.FPS)
    y = 148 + i * 20
    p.setPen(QPen(col, 2.5))
    p.drawLine(660, y - 4, 674, y - 4)
    p.setPen(QColor(45, 45, 45))
    p.drawText(682, y, f"{a:g}")
    p.drawText(745, y, f"{tilt:7.2f}°")
    p.drawText(845, y, f"{peak:6.2f}°")
    p.drawText(935, y, f"{per:.3f}s")
p.setPen(QColor(120, 120, 120))
p.setFont(QFont("Consolas", 9))
p.drawText(660, 222, "倾斜角按 amp 长，周期逐位相同")

# 图例
lx = L
p.setFont(QFont("Consolas", 11))
for col, a in zip(COLORS, AMPS):
    p.setPen(QPen(col, 2.5))
    p.drawLine(lx, 620, lx + 34, 620)
    p.setPen(QColor(40, 40, 40))
    p.drawText(lx + 40, 625, f"amp = {a:g}")
    lx += 150

# 匀速窗口标注
p.setPen(QColor(90, 120, 170))
p.setFont(QFont("Microsoft YaHei", 9))
p.drawText(int(X(WIN_T0)) + 8, TP + 18, "匀速拖动 700px/s")

p.end()
img.save("tests/gain_curves.png")
print("saved tests/gain_curves.png")
for rows, a in zip(runs, AMPS):
    peak = max(abs(rw["theta_deg"]) for rw in rows)
    print(f"   amp {a:g}: max|θ| {peak:6.2f}°   自由摆周期 {S._decay_period(rows, 3.3):.3f}s")
