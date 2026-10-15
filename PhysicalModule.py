import math

from PyQt5.QtGui import QCursor
from PyQt5.QtCore import QPoint

class MousePhysic():
    def __init__(self, initPos: QPoint):
        # Initial Position
        self._x = initPos.x()
        self._y = initPos.y()
        # velocity
        self._vx = 0
        self._vy = 0
        # acceleration
        self._ax = 0
        self._ay = 0
        # Previous position
        self._prev_x = self._x
        self._prev_y = self._y
        # Previous velocity
        self._prev_vx = 0.0
        self._prev_vy = 0.0
        

    def _update(self, newPos: QCursor.pos):
        # The time reference is not second, but frame. One frame elapses each time this function is called.

        self._x, self._y = newPos.x(), newPos.y()

        # update velocity, should be divided by dt, but since the dt is one so no need
        self._vx = self._x - self._prev_x
        self._vy = self._y - self._prev_y
        print("Vol: ", self._vx, self._vy)

        # update acceleration
        self._ax = self._vx - self._prev_vx
        self._ay = self._vy - self._prev_vy

        print("acc: ",self._ax, self._ay)
        # update previous
        self._prev_x = self._x
        self._prev_y = self._y
        self._prev_vx, self._prev_vy = self._vx, self._vy

        return (self._vx, self._vy, self._ax, self._ay)


# ══════════════════════════════════════════════════════════════════════
#  拖拽摆动：绕抓取点的阻尼单摆
# ══════════════════════════════════════════════════════════════════════
# 这组参数是仿真里选定的「C 速度扶正」预设，实测：
#   跟手 23.8° / 抗抖 5.0° / 信噪比 4.8   （原始公式是 19.9° / 8.8° / 2.2）
SWING_G     = 6400.0   # 重力 px/s² —— 80Hz 下「1 像素/帧²」正好等于 6400
SWING_ZETA  = 0.35     # 阻尼比
SWING_KV    = 3.0      # 速度通道增益 1/s：匀速拖动也有恒定后仰，atan(kv*v/g)
SWING_KA    = 0.4      # 加速度通道增益
SWING_TAU   = 0.05     # 速度低通时间常数 s
SWING_TAU_A = 0.10     # 加速度低通时间常数 s —— 压掉手抖和差分噪声
SWING_MIN_R = 40.0     # 摆长下限：抓到贴图正中心时 r→0 会让 ω₀ 爆炸


class DragSwing:
    '''拖拽期间绕抓取点转的阻尼单摆。

    角度方程，θ 单位为弧度，θ=0 表示「从抓取点垂下」：

        θ'' = -(g/r)·sinθ - 2ζω₀·θ' - (ka·ax·cosθ - ka·ay·sinθ + kv·vx·cosθ - kv·vy·sinθ)/r

    θ 的初值取 -grabAngle，于是渲染角 (grabAngle + θ) 在 t=0 时正好是 0：
    贴图保持被你抓住时的姿态，之后重力把 θ 拉回 0，宠物就「转下去」了。

    整个东西按固定 dt 推进（项目里是 1/80），所以手感只取决于时间，不取决于
    鼠标事件有多密 —— 这正是它取代「dTheta = dx * amplifier」那套按每帧位移算
    角度的公式的原因：老公式在 125Hz 和 1000Hz 的设备上差了一百多倍。

    r 是抓取点到贴图中心的距离，也就是摆长。
    '''

    def __init__(self, grabLocal, spriteSize, grabAngleDeg,
                 g=SWING_G, zeta=SWING_ZETA, kv=SWING_KV, ka=SWING_KA,
                 tau=SWING_TAU, tau_a=SWING_TAU_A, amp=1.0):
        spriteWidth, spriteHeight = spriteSize
        #摆长：抓取点到贴图中心。贴图中心才是质心，窗口中心（含 MARGIN）不是
        self.r = max(math.hypot(-(spriteWidth/2.0 - grabLocal[0]),
                                spriteHeight/2.0 - grabLocal[1]), SWING_MIN_R)
        self.omega0 = math.sqrt(g / self.r)
        self.zeta, self.kv, self.ka = zeta, kv, ka
        self.tau, self.tau_a = tau, tau_a
        #amp 是 config.json 的 amplifier（摇晃强度），只乘驱动项，见 step()。
        #默认 1.0 = 老行为：1.0 在 IEEE754 下是乘法的恒等元，逐位等价。
        self.amp = float(amp)
        #t=0 时渲染角为 0，也就是保持被抓住的姿态
        self.theta = -math.radians(grabAngleDeg)
        self.omega = 0.0

        #光标信号链：位置 →低通(τ)→ 速度 →差分→ 加速度 →低通(τ_a)→ 输出
        self._px = self._py = None
        self._vx = self._vy = 0.0
        self._ax = self._ay = 0.0
        self._prev_vx = self._prev_vy = 0.0
        self._seeded = False
        self._samples = 0

    def step(self, cursorPos, dt):
        '''推进一帧，返回「在 grabAngle 之上还要再转多少度」。'''
        self._sample(cursorPos.x(), cursorPos.y(), dt)

        #两个通道叠加后投影到摆的切线方向。
        #amp 只乘在这里：重力回复项、阻尼项都不碰它，所以 ω₀、ζ、θ₀ 和平衡位置
        #全部与 amp 无关 —— 摇晃强度改的是幅度，不是摆的节奏。
        effectiveX = self.amp * (self.ka*self._ax + self.kv*self._vx)
        effectiveY = self.amp * (self.ka*self._ay + self.kv*self._vy)
        drive = -(effectiveX*math.cos(self.theta) - effectiveY*math.sin(self.theta)) / self.r
        alpha = (-(self.omega0 ** 2) * math.sin(self.theta)     #重力回复
                 - 2.0 * self.zeta * self.omega0 * self.omega   #阻尼
                 + drive)
        self.omega += alpha * dt        #先更新角速度
        self.theta += self.omega * dt   #再更新角度（半隐式欧拉，比显式稳）
        return math.degrees(self.theta)

    def _sample(self, x, y, dt):
        '''从整数像素坐标重建光标速度和加速度，每一环都在抗噪。'''
        if self._px is None:
            #第一个样本：只记位置
            self._px, self._py = x, y
            return

        rawVx = (x - self._px) / dt
        rawVy = (y - self._py) / dt
        if not self._seeded:
            #第一个速度直接采纳，不从 0 爬升 —— 那段爬升会被当成一个巨大的假加速度
            self._vx, self._vy = rawVx, rawVy
            self._seeded = True
        else:
            #低通系数由 dt 推导，不能写死，否则换帧率就变味
            alpha = 1.0 - math.exp(-dt / self.tau)
            self._vx += (rawVx - self._vx) * alpha
            self._vy += (rawVy - self._vy) * alpha

        if self._samples >= 1:
            #第二个样本起加速度才有意义
            rawAx = (self._vx - self._prev_vx) / dt
            rawAy = (self._vy - self._prev_vy) / dt
            if self.tau_a > 0.0:
                alphaA = 1.0 - math.exp(-dt / self.tau_a)
                self._ax += (rawAx - self._ax) * alphaA
                self._ay += (rawAy - self._ay) * alphaA
            else:
                self._ax, self._ay = rawAx, rawAy

        self._prev_vx, self._prev_vy = self._vx, self._vy
        self._px, self._py = x, y
        self._samples += 1


class PetPhyisc():
    def __init__(self, masspoint: QPoint, dragpoint: QPoint, mousepoint: QPoint):
        # mass point
        self.x = masspoint.x()
        self.y = masspoint.y()
        self.mass = 1

        # rotate attributes
        self.theta = 0
        self.inertia = 2
        # rotation velocity
        self.omega = 0
        # rotation acceleration
        self.alpha = 0

        # speed attributes
        self.vx, self.vy = 0, 0
        self.ax, self.ay = 0, 0

        # other attributes
        self.gravity = 1
        self.damping = 2

        self.MousePhysic = MousePhysic(mousepoint)
        self.dragpoint = dragpoint

