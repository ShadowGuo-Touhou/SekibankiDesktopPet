"""拖拽摆动仿真 —— 角度摆模型验证工具

和项目代码完全独立，不 import 任何项目模块，可随意修改或删除。

版本：只含「1+2」方案
    1. 加速度低通（tau_a）—— 补上信号链里唯一漏掉的那一环
    2. 速度通道（kv）—— 从「补充」升为可独立使用的主驱动
    （刚体+软约束那套已移除，见对话记录）

六种模式：
    python sim_pendulum.py            交互：用真实鼠标抓住贴图拖动，实时感受物理效果
    python sim_pendulum.py --demo     回放：自动跑一段脚本轨迹
    python sim_pendulum.py --gain     无窗口：amplifier（摇晃强度）扫描
    python sim_pendulum.py --trace    无窗口：打印 θ 曲线 + 量化噪声对比
    python sim_pendulum.py --probe    无窗口：查「匀速拖动时的持续摆荡」
    python sim_pendulum.py --compare  无窗口：跟手 vs 抗手抖，含两组参数扫描

物理模型（角度摆，绕抓取点转）：
    θ'' = -(g/r)·sin θ - 2ζω₀·θ' - amp·(ka·a_x·cos θ - ka·a_y·sin θ + kv·v)/r

    θ = 0 表示「从抓取点垂下」。θ 的初始值取 -grabAngle，这样渲染角
    (grabAngle + θ) 在 t=0 时正好为 0 —— 贴图保持你抓住它时的姿态；
    之后重力把 θ 拉回 0，宠物就「转下去」了。

    参数：
        r      抓取点到贴图中心的距离（px）
        g      重力加速度（px/s²）
        ζ      阻尼比
        ka     加速度通道增益
        kv     速度通道增益（1/s），>0 时匀速拖动也有恒定后仰
        amp    摇晃强度增益，只乘驱动项（见下）

    amp 是 config.json 里的 amplifier，**只乘驱动项**：
        · θ₀ = -grabAngle 不动 → 按下瞬间贴图的姿态与 amp 无关；
        · 重力回复项、阻尼项不动 → 自然频率 ω₀ 与阻尼比 ζ 不变，
          所以「摆动周期」和「每周期衰减比」都不随 amp 变；
        · 平衡位置（θ→0，渲染角 → grabAngle）也不随 amp 变。
    也就是说 amp 只放大「鼠标把宠物甩起来」的幅度，不改这个摆本身的性质。
    amp=1.0 与没有 amp 的老版本逐位等价。

按键（窗口模式）：
    [ ]   阻尼比 ζ          - =   重力 g
    , .   速度通道 kv       ; '   加速度通道 ka
    A S   摇晃强度 amp
    1~5   切预设            空格  暂停 / 继续
    R     重抓               D     切换 回放 / 交互
    ESC   退出
"""
import math
import sys

FPS = 80.0                 # 物理步长：和项目里的 _frame_rate = 1/80 对齐
DT = 1.0 / FPS

DEFAULT_R = 200.0          # 抓取点到质心距离 (px)
DEFAULT_G = 6400.0         # 重力 (px/s²)，≈ 80Hz 下的 1 px/帧²
DEFAULT_ZETA = 0.35        # 阻尼比
DEFAULT_KV = 0.0           # 速度通道增益 (1/s)
DEFAULT_KA = 1.0           # 加速度通道增益
DEFAULT_AMP = 1.0          # 摇晃强度增益（= config.json 的 amplifier），1.0 即老行为
MIN_R = 40.0               # r 的下限：抓到贴图正中心时 r→0 会让 ω₀ 爆炸
TAU = 0.05                 # 速度低通时间常数（秒）
TAU_A = 0.10               # 加速度低通时间常数（秒）—— 改动 1
DEMO_DURATION = 7.0

# 预设：(名称, ka, kv, tau_a, zeta)
PRESETS = [
    ("A 现状 原始加速度", 1.0, 0.0, 0.00, 0.35),
    ("B +加速度低通", 1.0, 0.0, 0.10, 0.35),
    ("C 速度扶正", 0.4, 3.0, 0.10, 0.35),
    ("D 纯速度驱动", 0.0, 5.0, 0.10, 0.35),
    ("E 高阻尼基准", 1.0, 0.0, 0.00, 0.70),
]


# ══════════════════════════════════════════════════════════════════════
#  纯物理
# ══════════════════════════════════════════════════════════════════════

class Pendulum:
    """绕固定支点的角度摆。theta 单位为弧度，0 = 垂下。"""

    def __init__(self, r=DEFAULT_R, g=DEFAULT_G, zeta=DEFAULT_ZETA,
                 kv=DEFAULT_KV, ka=DEFAULT_KA, theta0=0.0, amp=DEFAULT_AMP):
        self.r = max(float(r), MIN_R)
        self.g = float(g)
        self.zeta = float(zeta)
        self.kv = float(kv)
        self.ka = float(ka)
        self.amp = float(amp)                        # 只乘驱动项，见 step()
        self.omega0 = math.sqrt(self.g / self.r)     # 自然频率 rad/s
        self.theta = float(theta0)
        self.omega = 0.0

    def step(self, dt, ax=0.0, ay=0.0, vx=0.0, vy=0.0):
        """半隐式欧拉推进一步。

        ax/ay  支点加速度 (px/s²)  —— 加速度通道，gain = ka
        vx/vy  支点速度   (px/s)   —— 速度通道，  gain = kv
        amp                        —— 摇晃强度，整条驱动通道一起乘
        """
        #amp 只作用在这里：重力回复项、阻尼项都不碰它，所以 ω₀、ζ、θ₀、
        #平衡位置全部与 amp 无关。amp=1.0 时和没有 amp 的版本逐位等价。
        eff_ax = self.amp * (self.ka * ax + self.kv * vx)
        eff_ay = self.amp * (self.ka * ay + self.kv * vy)
        drive = -(eff_ax * math.cos(self.theta)
                  - eff_ay * math.sin(self.theta)) / self.r
        alpha = (-(self.omega0 ** 2) * math.sin(self.theta)      # 重力回复
                 - 2.0 * self.zeta * self.omega0 * self.omega     # 阻尼
                 + drive)
        self.omega += alpha * dt        # 先更新速度
        self.theta += self.omega * dt   # 再更新位置（半隐式，比显式欧拉稳）
        return self.theta

    @property
    def theta_deg(self):
        return math.degrees(self.theta)


class CursorSampler:
    """从「整数像素坐标」重建光标速度和加速度。

    信号链（每一环都在抗噪）：
        位置 ──低通(τ)──> 速度 ──差分──> 加速度 ──低通(τ_a)──> 输出

    三个要点：
      1. 速度做时间常数低通（系数由 dt 推导，不是固定常数）；
      2. 第一个速度直接采纳，不从 0 爬升 —— 否则那段爬升会被当成
         一个巨大的假加速度；
      3. 加速度再低通一层（τ_a），这是改动 1：压掉手抖和差分噪声。
         τ_a=0 时跳过，用来做对比。
    """

    def __init__(self, tau=TAU, tau_a=TAU_A):
        self.tau = tau
        self.tau_a = tau_a
        self.px = self.py = None
        self.vx = self.vy = 0.0
        self.ax = self.ay = 0.0          # 平滑后的加速度（对外输出）
        self._seeded = False
        self._last_vx = self._last_vy = 0.0
        self._samples = 0

    def update(self, x, y, dt):
        if self.px is None:                 # 第一个样本：只记位置
            self.px, self.py = x, y
            return 0.0, 0.0

        raw_vx = (x - self.px) / dt
        raw_vy = (y - self.py) / dt

        if not self._seeded:
            self.vx, self.vy = raw_vx, raw_vy     # 直接采纳，不从 0 爬
            self._seeded = True
        else:
            alpha = 1.0 - math.exp(-dt / self.tau)
            self.vx += (raw_vx - self.vx) * alpha
            self.vy += (raw_vy - self.vy) * alpha

        if self._samples >= 1:              # 第二个样本起，加速度才有意义
            raw_ax = (self.vx - self._last_vx) / dt
            raw_ay = (self.vy - self._last_vy) / dt
            if self.tau_a > 0.0:            # 改动 1：加速度低通
                alpha_a = 1.0 - math.exp(-dt / self.tau_a)
                self.ax += (raw_ax - self.ax) * alpha_a
                self.ay += (raw_ay - self.ay) * alpha_a
            else:
                self.ax, self.ay = raw_ax, raw_ay
        else:
            self.ax = self.ay = 0.0

        self._last_vx, self._last_vy = self.vx, self.vy
        self.px, self.py = x, y
        self._samples += 1
        return self.ax, self.ay


def grab_geometry(sprite_w, sprite_h, grab_local):
    """由抓取点算出「悬挂旋转角」和「质心距离 r」。

    角度公式和项目里 _changeDragAngle 的一致；但中心用的是**贴图中心**
    （物理上质心在贴图中心），而不是项目里的窗口中心（含 MARGIN）。
    """
    cx, cy = sprite_w / 2.0, sprite_h / 2.0
    ydiff = cy - grab_local[1]
    xdiff = -(cx - grab_local[0])
    r = math.hypot(xdiff, ydiff)
    if xdiff == 0:
        xdiff = 1.0
    ang = math.degrees(math.atan(ydiff / xdiff))
    grab_angle = ang - 90.0 if xdiff > 0 else ang + 90.0
    return grab_angle, max(r, MIN_R)


# ══════════════════════════════════════════════════════════════════════
#  脚本轨迹
# ══════════════════════════════════════════════════════════════════════

def build_demo_path(dt, duration=DEMO_DURATION):
    """速度剖面：静止 0.6s → 匀速右拖 2.0s → 减速 0.6s → 静止到结束。

    匀速段特意拉到 2 秒（≈2.2 个摆动周期），才能看出稳态倾角是多少。
    """
    x, y = 900.0, 500.0
    path = []
    t = 0.0
    while t < duration:
        if t < 0.6:
            v = 0.0
        elif t < 2.6:
            v = 700.0
        elif t < 3.2:
            v = 700.0 * (1.0 - (t - 2.6) / 0.6)
        else:
            v = 0.0
        x += v * dt
        path.append((x, y))
        t += dt
    return path


def simulate(path, r, g, zeta, theta0, quantize, kv=DEFAULT_KV,
             ka=DEFAULT_KA, tau=TAU, tau_a=TAU_A, dt=DT, amp=DEFAULT_AMP):
    """跑一遍物理，返回每帧记录。quantize=True 时坐标取整（模拟真实整数像素）。"""
    pend = Pendulum(r=r, g=g, zeta=zeta, kv=kv, ka=ka, theta0=theta0, amp=amp)
    sampler = CursorSampler(tau=tau, tau_a=tau_a)
    rows = []
    for i, (px, py) in enumerate(path):
        x = round(px) if quantize else px
        y = round(py) if quantize else py
        ax, ay = sampler.update(x, y, dt)
        pend.step(dt, ax, ay, sampler.vx, sampler.vy)
        rows.append({
            "i": i, "t": i * dt, "x": x, "y": y,
            "vx": sampler.vx, "ax": ax,
            "theta_deg": pend.theta_deg, "omega": pend.omega,
        })
    return rows


def analyse(rows):
    """从记录里抽出几个有意义的指标。"""
    out = {}
    out["theta0"] = rows[0]["theta_deg"]

    cross = None
    for row in rows:
        if row["theta_deg"] >= 0.0:
            cross = row["t"]
            break
    out["first_cross"] = cross

    if cross is not None:
        after = [r for r in rows if r["t"] > cross]
        out["overshoot"] = max((r["theta_deg"] for r in after), default=0.0)
    else:
        out["overshoot"] = 0.0

    const = [r for r in rows if 1.9 < r["t"] < 2.6]
    out["const_tilt"] = (sum(r["theta_deg"] for r in const) / len(const)
                         if const else 0.0)
    out["const_ripple"] = (max(r["theta_deg"] for r in const)
                           - min(r["theta_deg"] for r in const)) if const else 0.0

    last_big = 0.0
    for row in rows:
        if abs(row["theta_deg"]) > 2.0:
            last_big = row["t"]
    out["settle_after"] = last_big
    out["final"] = rows[-1]["theta_deg"]
    out["final_omega"] = rows[-1]["omega"]
    return out


# ══════════════════════════════════════════════════════════════════════
#  --trace 模式
# ══════════════════════════════════════════════════════════════════════

BAR_HALF = 30
GRAB_LOCAL = (110.0, 150.0)      # 抓在贴图左上偏（相当于抓到手）
SPRITE = 439.0


def _bar(theta_deg, scale=2.0):
    n = int(round(theta_deg / scale))
    n = max(-BAR_HALF, min(BAR_HALF, n))
    if n >= 0:
        return " " * BAR_HALF + "|" + "#" * n + " " * (BAR_HALF - n)
    return " " * (BAR_HALF + n) + "#" * (-n) + "|" + " " * BAR_HALF


def run_trace():
    grab_angle, r = grab_geometry(SPRITE, SPRITE, GRAB_LOCAL)
    theta0 = -math.radians(grab_angle)
    omega0 = math.sqrt(DEFAULT_G / r)

    print("=" * 80)
    print("角度摆仿真")
    print(f"  抓取点 {GRAB_LOCAL}  贴图 {SPRITE:.0f}x{SPRITE:.0f}")
    print(f"  grabAngle {grab_angle:7.2f}°    r {r:6.1f}px    θ₀ {-grab_angle:7.2f}°")
    print(f"  g {DEFAULT_G:.0f}px/s²   ζ {DEFAULT_ZETA}   kv {DEFAULT_KV}   "
          f"ω₀ {omega0:.2f}rad/s ({omega0/(2*math.pi):.2f}Hz, "
          f"周期 {2*math.pi/omega0:.2f}s)")
    print("=" * 80)

    path = build_demo_path(DT)
    rows = simulate(path, r, DEFAULT_G, DEFAULT_ZETA, theta0, quantize=True)

    print()
    print("  轨迹：静止 0~0.6s ｜ 匀速右拖 0.6~2.6s ｜ 减速 2.6~3.2s ｜ 静止 3.2~7s")
    print()
    print("  t(s)   光标x   vx(px/s)  ax(px/s²)    θ(deg)   θ 曲线（每格 2°）")
    print("  " + "-" * 76)
    for row in rows[::10]:
        print(f"  {row['t']:5.2f}  {row['x']:7.0f}  {row['vx']:8.0f}  "
              f"{row['ax']:9.0f}  {row['theta_deg']:8.2f}   "
              f"{_bar(row['theta_deg'])}")
    print("  " + "-" * 76)

    a = analyse(rows)
    print()
    print("关键行为：")
    print(f"  起始角（= -grabAngle）      {a['theta0']:8.2f}°")
    print(f"  重力转到垂下的时刻          {a['first_cross']:8.2f}s   "
          f"← 「受重力往下转」用掉的时间")
    print(f"  过冲峰值                    {a['overshoot']:8.2f}°")
    print(f"  匀速段平均倾角              {a['const_tilt']:8.2f}°   "
          f"(起伏 {a['const_ripple']:.2f}°)")
    print(f"  最后静止后 · 收敛用时       {a['settle_after']:8.2f}s   "
          f"（最后一次 |θ|>2° 的时刻）")
    print(f"  末帧 θ / ω                  {a['final']:8.2f}° / "
          f"{a['final_omega']:.4f} rad/s")

    ideal = simulate(path, r, DEFAULT_G, DEFAULT_ZETA, theta0, quantize=False)
    diffs = [abs(x["theta_deg"] - y["theta_deg"]) for x, y in zip(ideal, rows)]
    print()
    print("─" * 80)
    print("对比 1 · 量化噪声（同一条轨迹，浮点坐标 vs 整数坐标）")
    print(f"    最大偏差 {max(diffs):6.3f}°    平均偏差 {sum(diffs)/len(diffs):6.3f}°"
          f"    末帧偏差 {diffs[-1]:6.3f}°")
    verdict = "✅ 可忽略，角摆自己把量化噪声滤掉了" if max(diffs) < 1.0 \
        else "⚠️ 偏大，需要加低通"
    print(f"    {verdict}")

    print()
    print("─" * 80)
    print("对比 2 · 驱动方式（kv = 速度通道增益）")
    print("    kv      匀速段平均倾角   匀速段起伏   过冲峰值   收敛时刻")
    for kv in (0.0, 1.0, 2.0, 4.0):
        rr = simulate(path, r, DEFAULT_G, DEFAULT_ZETA, theta0,
                      quantize=True, kv=kv)
        aa = analyse(rr)
        print(f"    {kv:4.1f}   {aa['const_tilt']:12.2f}°  "
              f"{aa['const_ripple']:10.2f}°  {aa['overshoot']:8.2f}°  "
              f"{aa['settle_after']:8.2f}s")
    print("    kv=0 是纯物理（匀速不倾斜）；kv>0 时匀速拖动也有恒定后仰")

    print()
    print("─" * 80)
    print("对比 3 · 阻尼比 ζ")
    print("    ζ       过冲峰值    收敛时刻    末帧 ω")
    for z in (0.15, 0.25, 0.35, 0.5, 0.8):
        rr = simulate(path, r, DEFAULT_G, z, theta0, quantize=True)
        aa = analyse(rr)
        print(f"    {z:4.2f}   {aa['overshoot']:9.2f}°  {aa['settle_after']:9.2f}s  "
              f"{aa['final_omega']:9.4f}")
    print("=" * 80)


# ══════════════════════════════════════════════════════════════════════
#  --probe 模式：专查「匀速拖动时的持续摆荡」
# ══════════════════════════════════════════════════════════════════════

def build_const_path(dt, v, ramp=0.3, hold=3.0):
    """先匀加速到 v（ramp 秒），再匀速保持（hold 秒）。"""
    x, y = 900.0, 500.0
    path = []
    t = 0.0
    while t < ramp + hold:
        sp = v * (t / ramp) if t < ramp else v
        x += sp * dt
        path.append((x, y))
        t += dt
    return path


def _ripple(rows, t0, t1):
    """指定时间窗内的 θ 峰谷差（度）。"""
    tail = [r["theta_deg"] for r in rows if t0 <= r["t"] < t1]
    return max(tail) - min(tail) if tail else 0.0


def run_probe():
    grab_angle, r = grab_geometry(SPRITE, SPRITE, GRAB_LOCAL)
    omega0 = math.sqrt(DEFAULT_G / r)
    print("=" * 88)
    print("诊断：匀速拖动时的持续摆荡")
    print("  从「已垂好」出发（θ₀=0），先加速 0.3s 到 v，再匀速保持到 3.3s")
    print("  三个时间窗分开统计 —— 起伏随时间衰减 = 起步冲击的余摆，不是持续驱动")
    print(f"  r {r:.1f}px   ω₀ {omega0:.2f}rad/s = {omega0/(2*math.pi):.2f}Hz   "
          f"周期 {2*math.pi/omega0:.2f}s   ζ {DEFAULT_ZETA}")
    print("=" * 88)
    print()
    print("             |-------- 浮点坐标 --------|  |-------- 整数坐标 --------|")
    print("  v(px/s)    | 1.2-2.0  2.0-2.8  2.8-3.3 |  1.2-2.0  2.0-2.8  2.8-3.3 |")
    print("  " + "-" * 76)

    for v in range(300, 1251, 50):
        path = build_const_path(DT, v)
        cells = []
        for quant in (False, True):
            rows = simulate(path, r, DEFAULT_G, DEFAULT_ZETA, 0.0,
                            quantize=quant, kv=0.0)
            cells.append([_ripple(rows, 1.2, 2.0),
                          _ripple(rows, 2.0, 2.8),
                          _ripple(rows, 2.8, 3.3)])
        print(f"  {v:6d}     | {cells[0][0]:7.2f}  {cells[0][1]:7.2f}  "
              f"{cells[0][2]:7.2f} |  {cells[1][0]:7.2f}  {cells[1][1]:7.2f}  "
              f"{cells[1][2]:7.2f} |")

    print("  " + "-" * 76)
    print()
    print("  读法：")
    print("    · 若「2.8-3.3s」远小于「1.2-2.0s」→ 起伏在衰减 = 起步冲击的余摆")
    print("    · 若三个窗口差不多大        → 有东西在持续驱动它，需要找源头")
    print("    · 浮点 vs 整数 两栏若接近   → 和整数取整无关")
    print("=" * 88)


def build_tremor_path(dt, v=600.0, duration=4.5):
    """匀速拖动 + 手抖：在速度上叠三个正弦分量（模拟人手无法保持匀速）。"""
    x, y = 900.0, 500.0
    path = []
    t = 0.0
    while t < duration:
        base = v * min(1.0, t / 0.25)                 # 0.25s 起手
        tremor = (50.0 * math.sin(2 * math.pi * 1.3 * t)
                  + 30.0 * math.sin(2 * math.pi * 3.1 * t + 1.0)
                  + 20.0 * math.sin(2 * math.pi * 6.7 * t + 2.0))
        x += (base + tremor) * dt
        path.append((x, y))
        t += dt
    return path


# ══════════════════════════════════════════════════════════════════════
#  --compare 模式
# ══════════════════════════════════════════════════════════════════════

def _resp_jit(spec, ramp, tremor, r, grab_angle, amp=DEFAULT_AMP):
    """跑两条轨迹，返回 (跟手, 抗抖)。"""
    name, ka, kv, tau_a, zeta = spec
    rr = simulate(ramp, r, DEFAULT_G, zeta, 0.0, quantize=True,
                  kv=kv, ka=ka, tau_a=tau_a, amp=amp)
    resp = max(abs(x["theta_deg"]) for x in rr if x["t"] < 0.8)
    rj = simulate(tremor, r, DEFAULT_G, zeta, 0.0, quantize=True,
                  kv=kv, ka=ka, tau_a=tau_a, amp=amp)
    return resp, _ripple(rj, 2.5, 4.5)


def run_compare():
    grab_angle, r = grab_geometry(SPRITE, SPRITE, GRAB_LOCAL)
    print("=" * 88)
    print("对比：跟随手感 vs 抗手抖")
    print("  跟手   = 一次刻意起手（0→600px/s 用 0.25s）期间的最大倾角，越大越跟手")
    print("  抗抖   = 匀速拖动叠加手抖（1.3/3.1/6.7Hz）后的稳态起伏，越小越稳")
    print("  信噪比 = 跟手 / 抗抖，越大说明「分得开刻意动作和手抖」")
    print("  ※ 手抖模型是估计值，绝对数字别当真，配置之间的相对优劣可信")
    print("=" * 88)
    print()
    print("  配置                    ka    kv  τ_a    ζ     跟手      抗抖    信噪比")
    print("  " + "-" * 82)

    ramp = build_const_path(DT, 600.0, ramp=0.25, hold=1.2)
    tremor = build_tremor_path(DT)

    for spec in PRESETS:
        name, ka, kv, tau_a, zeta = spec
        resp, jit = _resp_jit(spec, ramp, tremor, r, grab_angle)
        snr = resp / jit if jit > 1e-6 else 999.0
        print(f"  {name:<20}  {ka:4.1f}  {kv:4.1f}  {tau_a:4.2f}  {zeta:4.2f}  "
              f"{resp:7.2f}°  {jit:7.2f}°  {snr:8.1f}")

    print("  " + "-" * 82)
    print()
    print("  注意：A 和 E 用同样的输入，只有 ζ 不同 —— 对比它们就能看出")
    print("        「靠加大阻尼压抖动」牺牲了多少跟手幅度。")

    # ---- 扫描 1：保留纯加速度驱动，只调加速度低通 ----
    print()
    print("─" * 88)
    print("扫描 1 · 保留「匀速不倾斜」：ka=1, kv=0, ζ=0.35，只调 τ_a")
    print("    τ_a      跟手      抗抖    信噪比")
    for tau_a in (0.00, 0.04, 0.08, 0.12, 0.16, 0.22, 0.30):
        spec = ("", 1.0, 0.0, tau_a, 0.35)
        resp, jit = _resp_jit(spec, ramp, tremor, r, grab_angle)
        print(f"   {tau_a:5.2f}  {resp:8.2f}°  {jit:7.2f}°  "
              f"{resp/jit if jit > 1e-6 else 999:8.1f}")

    # ---- 扫描 2：纯速度驱动，调 kv ----
    print()
    print("─" * 88)
    print("扫描 2 · 纯速度驱动：ka=0, τ_a=0.10, ζ=0.35，调 kv")
    print("    kv       跟手      抗抖    信噪比    恒定后仰")
    for kv in (1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 9.0):
        spec = ("", 0.0, kv, 0.10, 0.35)
        resp, jit = _resp_jit(spec, ramp, tremor, r, grab_angle)
        steady = math.degrees(math.atan(kv * 600.0 / DEFAULT_G))
        print(f"   {kv:5.1f}  {resp:8.2f}°  {jit:7.2f}°  "
              f"{resp/jit if jit > 1e-6 else 999:8.1f}   {steady:6.1f}°")
    print("=" * 88)


# ══════════════════════════════════════════════════════════════════════
#  --gain 模式：amplifier（摇晃强度）扫描
# ══════════════════════════════════════════════════════════════════════

GAIN_SWEEP = (0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0)
SAFE_SWEEP = (1.0, 2.0, 4.0, 8.0, 16.0)


def _decay_period(rows, t0):
    """t0 之后的自由摆过零间隔中位数（秒）。"""
    cross, prev = [], None
    for r in rows:
        th = r["theta_deg"]
        if prev is not None and prev * th < 0.0 and r["t"] >= t0:
            cross.append(r["t"])
        prev = th
    if len(cross) < 3:
        return float("nan")
    gaps = sorted(b - a for a, b in zip(cross, cross[1:]))
    return gaps[len(gaps) // 2]


def _peak_ratios(rows, t0):
    """t0 之后相邻极值的幅度比中位数（每半个周期衰减一次）。"""
    seq = [r["theta_deg"] for r in rows if r["t"] >= t0]
    ext = []
    for i in range(1, len(seq) - 1):
        if (seq[i] - seq[i - 1]) * (seq[i + 1] - seq[i]) < 0.0:
            ext.append(abs(seq[i]))
    ratios = [b / a for a, b in zip(ext, ext[1:]) if a > 0.5]
    if not ratios:
        return float("nan")
    ratios.sort()
    return ratios[len(ratios) // 2]


def _read_project_amp():
    """读项目里真实的 config.json amplifier，读不到就返回 None。"""
    import json
    for path in ("assets/Settings/config.json", "../assets/Settings/config.json"):
        try:
            with open(path, encoding="utf-8") as f:
                return float(json.load(f).get("amplifier", DEFAULT_AMP))
        except Exception:
            continue
    return None


def run_gain():
    grab_angle, r = grab_geometry(SPRITE, SPRITE, GRAB_LOCAL)
    theta0 = -math.radians(grab_angle)
    omega0 = math.sqrt(DEFAULT_G / r)
    spec = PRESETS[2]                     # C 速度扶正 = PhysicalModule 里那套 SWING_*
    name, ka, kv, tau_a, zeta = spec

    ramp = build_const_path(DT, 600.0, ramp=0.25, hold=1.2)
    tremor = build_tremor_path(DT)
    demo = build_demo_path(DT)

    print("=" * 88)
    print("amplifier（摇晃强度）扫描 · 方案 B —— amp 只乘驱动项")
    print(f"  基准预设 [{name}]  ka {ka}  kv {kv}  tau_a {tau_a}  zeta {zeta}"
          f"   ← 与 PhysicalModule 的 SWING_* 一致")
    print(f"  r {r:.1f}px   ω₀ {omega0:.2f}rad/s   自由周期 {2*math.pi/omega0:.3f}s")
    cur = _read_project_amp()
    if cur is not None:
        print(f"  当前 config.json 里的 amplifier = {cur:g}")
    print("=" * 88)

    # ---- 1 · 放大效果 ----
    data = []
    for amp in GAIN_SWEEP:
        resp, jit = _resp_jit(spec, ramp, tremor, r, grab_angle, amp=amp)
        data.append((amp, resp, jit))
    ref = next(d for d in data if abs(d[0] - 1.0) < 1e-9)

    print()
    print("─ 1 · 跟手 / 抗抖随 amp 的放大比例（同一条轨迹，只改 amp）")
    print("    amp     跟手(°)   ×基准    抗抖(°)   ×基准    信噪比")
    for amp, resp, jit in data:
        snr = resp / jit if jit > 1e-6 else 999.0
        print(f"   {amp:5.2f}   {resp:8.2f}   {resp/ref[1]:6.2f}   {jit:8.2f}   "
              f"{jit/ref[2]:6.2f}   {snr:8.1f}")
    print("    跟手 = 有意起手时的最大倾角（越大越跟手）")
    print("    抗抖 = 匀速拖动叠手抖后的稳态起伏（越小越稳）")
    print("    读法：×基准 ≈ amp → 纯线性放大；信噪比不变 → 手抖也被同比放大")
    print("          （这就是 amp 拉大的代价：不是变「抖」，而是抖得更大声）")

    # ---- 2 · 不变量 ----
    print()
    print("─ 2 · 不变量（必须跨 amp 完全一致，否则就是把摆本身改掉了）")
    print("    amp    起始角(°)  重力转下(s)  自由摆周期(s)  半周期衰减比")
    inv = []
    for amp in GAIN_SWEEP:
        rows = simulate(demo, r, DEFAULT_G, zeta, theta0, quantize=True,
                        kv=kv, ka=ka, tau_a=tau_a, amp=amp)
        a = analyse(rows)
        inv.append((amp, a, _decay_period(rows, 3.3), _peak_ratios(rows, 3.3)))
        print(f"   {amp:5.2f}  {a['theta0']:9.2f}  {a['first_cross']:10.3f}  "
              f"{inv[-1][2]:12.3f}  {inv[-1][3]:12.3f}")
    print("      · 起始角不变  → θ₀ = -grabAngle 没被碰，按下瞬间不会跳姿态")
    print("      · 周期不变    → ω₀ 没被碰，amp 不是靠「摆得更快」装出来的")
    print("      · 衰减比不变  → ζ 没被碰，回正的手感不会被 amp 带偏")

    # ---- 2b · 幅度类指标（这些本来就该随 amp 变） ----
    print()
    print("─ 2b · 幅度（匀速 700px/s 拖动的倾角 = 最影响手感的那个数）")
    print("    amp    匀速段均值(°)  解析 sinθ  过冲峰值(°)  收敛(s)    max|θ|(°)")
    for amp, a, _, _ in inv:
        rows = simulate(demo, r, DEFAULT_G, zeta, theta0, quantize=True,
                        kv=kv, ka=ka, tau_a=tau_a, amp=amp)
        mx = max(abs(x["theta_deg"]) for x in rows)
        #稳态解析：驱动 = 重力 → sinθ = amp·kv·v/g；超过 1 就是理论上压不住了
        sin_eq = amp * kv * 700.0 / DEFAULT_G
        flag = "  ← 解析已饱和" if sin_eq >= 1.0 else ""
        print(f"   {amp:5.2f}  {a['const_tilt']:13.2f}  {min(sin_eq, 9.99):9.2f}  "
              f"{a['overshoot']:10.2f}  {a['settle_after']:8.2f}  {mx:10.2f}{flag}")
    print("    「匀速段均值」是 1.9~2.6s 的实测平均，不是稳态 —— 大 amp 下它明显低于解析值，")
    print("    因为非线性区趋近很慢，2 秒内还没摆到位（这是真实行为，仿真没骗你）。")
    print("    「解析 sinθ」= amp·kv·v/g，是「若给足时间」的稳态；它 ≥1 就意味着")
    print("    驱动已经压过重力、理论上会被拖到水平 —— 幅度增益的物理天花板就在这。")
    print("    过冲峰值与收敛时刻随 amp 变大是应该的，不是 bug。")

    # ---- 3 · 安全边界 ----
    print()
    print("─ 3 · 安全边界（大幅时会不会甩过头 / 自旋）")
    print("    amp     max|θ|(°)   max|ω|(rad/s)     末帧 ω     越过 180°?")
    for amp in SAFE_SWEEP:
        rows = simulate(demo, r, DEFAULT_G, zeta, theta0, quantize=True,
                        kv=kv, ka=ka, tau_a=tau_a, amp=amp)
        mx = max(abs(x["theta_deg"]) for x in rows)
        mw = max(abs(x["omega"]) for x in rows)
        print(f"   {amp:5.1f}  {mx:10.2f}  {mw:13.2f}  {rows[-1]['omega']:10.4f}   "
              f"{'是 ⚠️ 会绕圈' if mx > 180.0 else '否'}")
    print("    末帧 ω → 0 表示摆收敛了；max|θ| 越过 180° 才是真的开始绕圈。")
    print("=" * 88)


# ══════════════════════════════════════════════════════════════════════
#  窗口模式（--demo 与交互）
# ══════════════════════════════════════════════════════════════════════

SPRITE_PATH = "assets/Sprite/dragRight.png"
SPRITE_W = SPRITE_H = 439          # 549 * 0.8，和项目里的缩放一致
MARGIN = 250                       # 旋转时不裁切

# θ 示波条：量程固定 ±180°，**不随幅度自适应** —— 自适应会把 amp 的放大效果归一化吃掉。
# 条带画在窗口最右侧一条竖条里（x ≥ width-232），那一带没有贴图也没有 HUD 文字。
TRAIL_SAMPLES = 170                # ≈2.1s 历史（80Hz）
TRAIL_SCALE = 2.2                  # px / 度
TRAIL_CLAMP = 180.0                # 度


def run_window(demo=False):
    from PyQt5.QtCore import Qt, QTimer, QPointF
    from PyQt5.QtGui import QPainter, QPixmap, QColor, QFont, QCursor
    from PyQt5.QtWidgets import QApplication, QWidget

    app = QApplication(sys.argv)

    class SimWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                                | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setFixedSize(SPRITE_W + 2 * MARGIN, SPRITE_H + 2 * MARGIN)

            self.sprite = QPixmap(SPRITE_PATH)
            if self.sprite.isNull():
                raise SystemExit(f"找不到贴图：{SPRITE_PATH}")
            self.sprite = self.sprite.scaled(SPRITE_W, SPRITE_H,
                                             Qt.KeepAspectRatio,
                                             Qt.SmoothTransformation)

            self.origin = (MARGIN, MARGIN)
            self.g = DEFAULT_G
            self.preset_idx = 1                   # 默认用 B：+加速度低通
            self.preset_name = PRESETS[1][0]
            _, self.ka, self.kv, self.tau_a, self.zeta = PRESETS[1]
            self.amp = DEFAULT_AMP                # 摇晃强度（config.json 的 amplifier）
            self.amp_min, self.amp_max = 0.1, 8.0
            self.paused = False
            self.demo_mode = demo
            self.grabbed = demo
            self.hint = ("D 模式 · 1~5 预设 · [ ] ζ · - = g · , . kv · "
                         "; ' ka · A S amp · R 重抓 · 空格 暂停 · ESC 退出")

            self._reset(demo)

            self.timer = QTimer(self)
            self.timer.setTimerType(Qt.PreciseTimer)
            self.timer.setInterval(int(DT * 1000))
            self.timer.timeout.connect(self._tick)
            self.timer.start()

        def _reset(self, demo, grab_local=None):
            if grab_local is None:
                grab_local = (GRAB_LOCAL if demo
                              else (SPRITE_W * 0.42, SPRITE_H * 0.30))
            self.grab_local = grab_local
            self.grab_angle, self.r = grab_geometry(SPRITE_W, SPRITE_H, grab_local)
            self.pend = Pendulum(r=self.r, g=self.g, zeta=self.zeta,
                                 kv=self.kv, ka=self.ka,
                                 theta0=-math.radians(self.grab_angle),
                                 amp=self.amp)
            self.sampler = CursorSampler(tau_a=self.tau_a)
            self.pivot = (self.origin[0] + grab_local[0],
                          self.origin[1] + grab_local[1])
            self.frame = 0
            self.demo_path = build_demo_path(DT) if demo else None
            self.trail = []
            if demo:
                self.move(600, 300)

        def _tick(self):
            if self.paused:
                return
            self.frame += 1

            if self.demo_mode:
                idx = (self.frame - 1) % len(self.demo_path)
                cx, cy = round(self.demo_path[idx][0]), round(self.demo_path[idx][1])
                self.grabbed = True
            else:
                pos = QCursor.pos()
                cx, cy = pos.x(), pos.y()
                if not self.grabbed:
                    self.pend.step(DT)            # 松手后只让摆动收敛
                    self.update()
                    return

            ax, ay = self.sampler.update(cx, cy, DT)
            self.pend.step(DT, ax, ay, self.sampler.vx, self.sampler.vy)

            #pivot 在 demo 模式下来自 GRAB_LOCAL 的浮点抓取点，move() 只吃 int，
            #所以这里必须取整（交互模式下从 Qt 事件拿的坐标本来就是 int，取整是无害的）
            self.move(int(round(cx - self.pivot[0])), int(round(cy - self.pivot[1])))
            self.trail.append(self.pend.theta_deg)
            if len(self.trail) > TRAIL_SAMPLES:
                self.trail.pop(0)
            self.update()

        def mousePressEvent(self, e):
            if e.button() == Qt.LeftButton and not self.demo_mode:
                self._reset(False, (e.pos().x() - self.origin[0],
                                    e.pos().y() - self.origin[1]))
                self.grabbed = True
            e.accept()

        def mouseReleaseEvent(self, e):
            self.grabbed = False       # 松手：停止跟随，但摆动继续（看它收敛）
            e.accept()

        def keyPressEvent(self, e):
            k = e.key()
            if k == Qt.Key_Escape:
                self.timer.stop()
                app.quit()
            elif Qt.Key_1 <= k < Qt.Key_1 + len(PRESETS):
                self.preset_idx = k - Qt.Key_1
                self.preset_name = PRESETS[self.preset_idx][0]
                _, self.ka, self.kv, self.tau_a, self.zeta = PRESETS[self.preset_idx]
                self._apply()
                self._reset(self.demo_mode)      # 换配置就重来一次，好对比
            elif k == Qt.Key_BracketLeft:
                self.zeta = max(0.02, self.zeta - 0.05); self._apply()
            elif k == Qt.Key_BracketRight:
                self.zeta = min(1.5, self.zeta + 0.05); self._apply()
            elif k == Qt.Key_Minus:
                self.g = max(800.0, self.g * 0.8); self._apply()
            elif k == Qt.Key_Equal:
                self.g = min(60000.0, self.g * 1.25); self._apply()
            elif k == Qt.Key_Comma:
                self.kv = max(0.0, self.kv - 0.5); self._apply()
            elif k == Qt.Key_Period:
                self.kv = min(12.0, self.kv + 0.5); self._apply()
            elif k == Qt.Key_Semicolon:
                self.ka = max(0.0, round(self.ka - 0.1, 2)); self._apply()
            elif k == Qt.Key_Apostrophe:
                self.ka = min(2.0, round(self.ka + 0.1, 2)); self._apply()
            elif k == Qt.Key_A:
                self.amp = max(self.amp_min, round(self.amp - 0.25, 2))
                self._apply()
            elif k == Qt.Key_S:
                self.amp = min(self.amp_max, round(self.amp + 0.25, 2))
                self._apply()
            elif k == Qt.Key_R:
                self._reset(self.demo_mode)
            elif k == Qt.Key_Space:
                self.paused = not self.paused
            elif k == Qt.Key_D:
                self.demo_mode = not self.demo_mode
                self.grabbed = self.demo_mode
                self._reset(self.demo_mode)
            e.accept()

        def _apply(self):
            self.pend.g = self.g
            self.pend.zeta = self.zeta
            self.pend.kv = self.kv
            self.pend.ka = self.ka
            self.pend.amp = self.amp            # 只乘驱动项，重力/阻尼不受影响
            self.sampler.tau_a = self.tau_a
            self.pend.omega0 = math.sqrt(self.g / self.pend.r)

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)

            p.save()
            p.translate(self.pivot[0], self.pivot[1])
            p.rotate(self.grab_angle + self.pend.theta_deg)
            p.translate(-self.pivot[0], -self.pivot[1])
            p.drawPixmap(self.origin[0], self.origin[1], self.sprite)
            p.restore()

            p.setPen(QColor(120, 200, 255, 160))
            p.drawLine(QPointF(self.pivot[0], self.pivot[1]),
                       QPointF(self.pivot[0], self.pivot[1] + 170))
            p.setBrush(QColor(255, 80, 80))
            p.setPen(QColor(255, 255, 255))
            p.drawEllipse(QPointF(*self.pivot), 7.0, 7.0)

            self._draw_hud(p)

        def _draw_hud(self, p):
            w0 = self.pend.omega0
            lines = [
                f"{'DEMO 回放' if self.demo_mode else '交互 · 拖我'}"
                f"{'  暂停' if self.paused else ''}"
                f"{'' if self.grabbed else '  (已松手，仅收敛)'}",
                f"[{self.preset_name}]",
                f"g {self.g:7.0f}px/s²   grabAngle {self.grab_angle:7.2f}°   r {self.r:6.1f}px",
                f"ka {self.ka:.1f}   kv {self.kv:.1f}   tau_a {self.tau_a:.2f}   zeta {self.zeta:.2f}",
                f"amp {self.amp:5.2f}   ← 摇晃强度（A S 调，只乘驱动项）",
                f"w0 {w0:6.2f}rad/s   周期 {2*math.pi/w0:.2f}s   ← 与 amp 无关",
                f"θ {self.pend.theta_deg:7.2f}°   ω {self.pend.omega:7.2f}rad/s",
                "渲染角 = grabAngle + θ（θ 已含 amp，渲染处不再乘）",
            ]
            p.setFont(QFont("Consolas", 11))
            for i, line in enumerate(lines):
                p.setPen(QColor(10, 10, 10, 220))
                p.drawText(13, 19 + i * 17, line)
                p.setPen(QColor(255, 255, 255, 235))
                p.drawText(12, 18 + i * 17, line)

            if self.trail:
                #竖条：x ≥ bx 那一带没有贴图也没有 HUD 文字，可以占满整个高度
                bx = self.width() - 232
                by = self.height() // 2
                span = TRAIL_CLAMP * TRAIL_SCALE

                p.setPen(QColor(190, 190, 190, 70))
                for tick in (-180, -90, 0, 90, 180):
                    ty = int(by - tick * TRAIL_SCALE)
                    p.drawLine(bx + 46, ty, bx + 224, ty)
                p.setPen(QColor(200, 200, 200, 160))
                p.setFont(QFont("Consolas", 9))
                for tick in (-180, -90, 90, 180):
                    p.drawText(bx + 2, int(by - tick * TRAIL_SCALE) + 4, f"{tick:4d}°")
                p.setPen(QColor(230, 90, 90, 150))
                p.drawText(bx + 2, by + 4, "   0°")

                #量程固定，所以幅度变大就是曲线变高 —— 这正是要看的东西
                p.setPen(QColor(120, 200, 255, 220))
                prev = None
                for i, th in enumerate(self.trail):
                    px = bx + 50 + i
                    py = by - max(-span, min(span, th * TRAIL_SCALE))
                    if prev is not None:
                        p.drawLine(int(px - 1), int(prev), int(px), int(py))
                    prev = py
                p.setPen(QColor(190, 190, 190, 120))
                p.drawText(bx + 50, by - span - 6, "θ 曲线 · 量程固定 ±180°")

            p.setPen(QColor(200, 200, 200, 200))
            p.setFont(QFont("Consolas", 9))
            p.drawText(12, self.height() - 12, self.hint)

    win = SimWindow()
    win.show()
    return app.exec_()


# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--trace":
        run_trace()
    elif mode == "--gain":
        run_gain()
    elif mode == "--probe":
        run_probe()
    elif mode == "--compare":
        run_compare()
    elif mode == "--demo":
        sys.exit(run_window(demo=True))
    else:
        sys.exit(run_window(demo=False))
