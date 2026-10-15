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

