"""工具栏（小窗口）模式的实现。

宠物住在一个边长 windowSide 的方块窗口里，窗口跟着宠物在桌面上移动。窗口中心在拖拽时
同时充当旋转枢轴，所以窗口按「贴图任意角度、任意抓取点都不被裁剪」的最坏情况开边长
（贴图对角线），贴图居中放在里面。

全屏模式是另一套完全不同的做法——窗口固定覆盖主屏、宠物在窗口内部移动——因此它单独
一个文件，实现在 FullScreenMode.py（将来）。

--------------------------------------------------------------------------
本模式里两个坐标系的换算
--------------------------------------------------------------------------

    宠物位置（接口口径）：贴图左上角的**屏幕坐标**
    窗口位置（本模式专有）：方块窗口左上角的屏幕坐标

        pet_top_left = window_top_left + (spriteInset, spriteInset)

接口只进出「宠物位置」，窗口位置是本文件的私事。
"""

import random
from math import ceil, floor, hypot, cos, sin, radians

from PyQt5.QtCore import QPoint, QRect, QSize, Qt

from PetMode import PetMode


class TrayMode(PetMode):
    '''小窗口模式：窗口 = 一个跟着宠物跑的方块。'''

    def __init__(self, pet):
        super().__init__(pet)
        #窗口边长，以及贴图居中后左右各留的空白。由 applyScale 填。
        self.windowSide = None
        self.spriteInset = None

#-- 生命周期 --------------------------------------------------------------------------------------------

    def configureWindow(self):
        '''按 showInTaskbar 决定窗口是普通顶层窗口还是子窗口。

        Qt.Window 会长出任务栏条目，录屏软件（OBS 等）也才能把它列成窗口捕获源；
        SubWindow 在 Windows 上带 WS_EX_TOOLWINDOW，两处都不出现。无边框、透明、
        置顶三件事不受影响。
        尺寸不在这里定——那时贴图还没建好，留给 applyScale。
        用 .get 读，老 config.json 没有这个键时按「关」处理。
        '''
        if self.pet._settingMenu.getConfig().get('showInTaskbar', False):
            self.pet.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window)
        else:
            self.pet.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)

    def applyScale(self, at=None):
        '''按当前 _petImageSize 重算窗口尺寸，并重排标签。

        窗口要够大以容纳任意抓取点、任意角度的旋转贴图：窗口中心就是旋转枢轴，
        所以窗口只需够到最远的角，也就是对角线。一次到位意味着拖拽过程中永远
        不需要再改窗口尺寸。

        参数 at: QPoint 或 None。非 None 表示顺便把窗口挪到这个屏幕坐标，供启动时
                 一次调用完成定位+定尺寸，避免"先 resize 后 move"两次 SetWindowPos
                 之间的闪帧。
        '''
        #get the width&height after resize
        newWidth = int(self.pet.ORGINALWIDTH*self.pet._petImageSize)
        newHeight = int(self.pet.ORGINALHEIGHT*self.pet._petImageSize)
        #rescale petImage with it.
        self.pet.petImage.setScaledSize(QSize(newWidth, newHeight))
        side = 2*int(ceil(hypot(newWidth, newHeight)))
        self.windowSide = side
        self.spriteInset = (side - newWidth)//2
        if at is None:
            self.pet.resize(side, side)
        else:
            #Position and size in one call, for the rare resize that still happens (startup
            #and a tray scale change)
            self.pet.setGeometry(at[0], at[1], side, side)
        #The label covers the whole window and centres the movie, matching what paintEvent
        #does with the drag sprite
        self.pet.petLabel.setAlignment(Qt.AlignCenter)
        self.pet.petLabel.resize(side, side)
        self.pet.petLabel.move(0, 0)

#-- 位置 ------------------------------------------------------------------------------------------------

    def petRect(self):
        '''宠物贴图当前的屏幕矩形（未旋转）。

        本模式下窗口中心就是贴图中心，所以贴图左上角 = 窗口左上角 + 内缩。
        '''
        size = self.petSize()
        return QRect(self.pet.pos().x() + self.spriteInset,
                     self.pet.pos().y() + self.spriteInset,
                     size.width(), size.height())

    def placePetAt(self, x, y):
        '''把宠物贴图左上角放到屏幕坐标 (x, y)。

        本模式下「移动宠物」就是「移动窗口」：把窗口挪到贴图应该在的位置再减掉内缩。
        '''
        self.pet.move(int(x) - self.spriteInset, int(y) - self.spriteInset)

    def randomPetPos(self):
        '''屏幕内一个随机的、保证整只宠物不出屏的落点（宠物左上角）。'''
        screen = self.screenRect()
        size = self.petSize()
        return QPoint(random.randint(screen.left(), screen.right() - size.width()),
                      random.randint(screen.top(), screen.bottom() - size.height()))

    def petBounds(self):
        '''宠物当前的旋转包围盒，屏幕坐标。

        站立时就是 petRect()。拖拽时贴图绕枢轴转，所以取四个角旋转后的包围盒，
        基准是枢轴在屏幕上的位置。
        '''
        if not self.isDragging():
            return QRect(self.petRect())
        left, top, right, bottom = self.reachFromPivot()
        px = self.pet.pos().x() + self.pet._pivotOffset.x()
        py = self.pet.pos().y() + self.pet._pivotOffset.y()
        #Round OUTWARDS, never towards the middle: a bounding box that is a pixel short of
        #the sprite is a bounding box that lies about what it covers.
        x0, y0 = floor(px + left), floor(py + top)
        x1, y1 = ceil(px + right), ceil(py + bottom)
        return QRect(x0, y0, x1 - x0, y1 - y0)

#-- 拖拽 ------------------------------------------------------------------------------------------------

    def isDragging(self):
        '''当前是否处于「按拖拽方式绘制」的状态。

        本模式没有独立的拖拽标志：_dragRadius 只在 prepareDrag 里被设、在 endDrag 里
        被清，所以它是否是 None 就等价于「在不在拖拽态」。
        '''
        return self.pet._dragRadius is not None

    def prepareDrag(self, grabGlobalPos):
        '''按下：把抓取点记成旋转枢轴。

        窗口在 applyScale 里就已经开到了最坏情况，所以这里**不移动任何东西**——
        这正是"点一下宠物不会跳"的原因。

        抓取点要换算成窗口坐标存进 _drag_pos：paintEvent 的旋转、抓取角计算、
        包围盒都按窗口坐标做。
        '''
        self.pet._drag_pos = QPoint(grabGlobalPos.x() - self.pet.pos().x(),
                                    grabGlobalPos.y() - self.pet.pos().y())
        self.pet._dragRadius = self.windowSide//2
        self.pet._spriteOrigin = (self.spriteInset, self.spriteInset)
        #The grab point in window coordinates IS the pivot, and that is what _drag_pos holds
        self.pet._pivotOffset = self.pet._drag_pos

    def followCursor(self, cursorScreenPos):
        '''把枢轴停到光标下，并把整只宠物夹在屏幕内。

        抓取点在窗口坐标里就是枢轴，所以把窗口中心停到光标上，任何旋转角下被抓的
        那一块都还在鼠标底下。这就是取代旧 _drag_pos + "+15" 锚点修正的东西。
        '''
        #The window centre is the pivot, so reachFromPivot hands back the bounding box of
        #the rotated sprite around it; clamping the pivot by those four reach values keeps
        #the whole pet inside whatever angle it is hanging at.
        left, top, right, bottom = self.reachFromPivot()
        screen = self.screenRect()
        rightEdge = screen.x() + screen.width()
        bottomEdge = screen.y() + screen.height()
        pivot_x = cursorScreenPos.x()
        pivot_y = cursorScreenPos.y()
        if pivot_x < -left: pivot_x = -left
        elif pivot_x > rightEdge - right: pivot_x = rightEdge - right
        if pivot_y < -top: pivot_y = -top
        elif pivot_y > bottomEdge - bottom: pivot_y = bottomEdge - bottom
        self.pet.move(int(pivot_x - self.pet._pivotOffset.x()),
                      int(pivot_y - self.pet._pivotOffset.y()))

    def endDrag(self):
        '''退出拖拽的几何收尾：把窗口放回它该在的地方。

        必须在调用方清掉 _spriteOrigin 之前调用——位置是拿它算的。
        没有窗口要回的时候（不在拖拽态）是空操作。
        '''
        if not self.isDragging():
            return
        keep_x, keep_y = self._dragExitWindowPos()
        self.pet.move(keep_x, keep_y)

    def spriteOriginInWindow(self):
        '''paintEvent 画旋转贴图时，贴图左上角在窗口里的位置。'''
        return QPoint(self.spriteInset, self.spriteInset)

    def pivotInWindow(self):
        '''paintEvent 的旋转枢轴，窗口坐标。'''
        return self.pet._pivotOffset

#-- 本模式私有 ------------------------------------------------------------------------------------------

    def reachFromPivot(self):
        '''贴图相对**枢轴**伸出多少：(left, top, right, bottom)。

        站立时枢轴就是窗口中心，也就是贴图中心，所以答案就是半个贴图。拖拽时把四个角
        按绘制角旋转后取包围盒。边界夹取和包围盒都用它。

        注意这是**枢轴相对量**，不是屏幕坐标——要屏幕矩形请用 petBounds()。
        '''
        W = int(self.pet.ORGINALWIDTH*self.pet._petImageSize)
        H = int(self.pet.ORGINALHEIGHT*self.pet._petImageSize)
        if not self.isDragging():
            return -W/2, -H/2, W/2, H/2
        #Grab point in sprite-local coordinates
        gx = self.pet._drag_pos.x() - self.spriteInset
        gy = self.pet._drag_pos.y() - self.spriteInset
        angle = radians(self.pet._dragAngleDeg)
        cosA, sinA = cos(angle), sin(angle)
        left = right = top = bottom = 0.0
        for cornerX, cornerY in ((0,0), (W,0), (0,H), (W,H)):
            offsetX = cornerX - gx
            offsetY = cornerY - gy
            rotX = offsetX*cosA - offsetY*sinA
            rotY = offsetX*sinA + offsetY*cosA
            left, right = min(left, rotX), max(right, rotX)
            top, bottom = min(top, rotY), max(bottom, rotY)
        return left, top, right, bottom

    def _dragExitWindowPos(self):
        '''退出拖拽时窗口该回到哪，按 (x, y) 返回，窗口坐标。

        缩小窗口会移动贴图：拖拽期间它坐在 _spriteOrigin，而站立布局把它放在
        (spriteInset, spriteInset)。算出这个差值，好让贴图留在屏幕上原处而不是跳一下。
        摆动可能把一两个角甩出屏幕，所以再按最短距离把窗口拉回来。
        '''
        keep_x = self.pet.pos().x() + self.pet._spriteOrigin[0] - self.spriteInset
        keep_y = self.pet.pos().y() + self.pet._spriteOrigin[1] - self.spriteInset
        #The sprite is upright again, so it occupies the plain spriteInset rect.
        W = int(self.pet.ORGINALWIDTH*self.pet._petImageSize)
        H = int(self.pet.ORGINALHEIGHT*self.pet._petImageSize)
        sprite_x = keep_x + self.spriteInset
        sprite_y = keep_y + self.spriteInset
        screen = self.screenRect()
        rightEdge = screen.x() + screen.width()
        bottomEdge = screen.y() + screen.height()
        if sprite_x < screen.left(): keep_x -= sprite_x - screen.left()
        elif sprite_x + W > rightEdge: keep_x -= (sprite_x + W) - rightEdge
        if sprite_y < screen.top(): keep_y -= sprite_y - screen.top()
        elif sprite_y + H > bottomEdge: keep_y -= (sprite_y + H) - bottomEdge
        return keep_x, keep_y
