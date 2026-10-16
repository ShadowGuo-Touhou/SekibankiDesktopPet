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
        #Window side length, and the blank border left around the centred sprite. Filled in
        #by applyScale.
        self.windowSide = None
        self.spriteInset = None
        #-- drag state --------------------------------------------------------------
        #Whether a drag is under way. isDragging() is the only way anything outside this
        #file asks, so how a drag is represented stays private to the mode.
        self.dragging = False
        #The grab point, in WINDOW coordinates. It doubles as the rotation pivot: the window
        #is never moved on press, so the grabbed spot is already sitting where it must be.
        #None while not dragging.
        self.grabPoint = None

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
        px = self.pet.pos().x() + self.grabPoint.x()
        py = self.pet.pos().y() + self.grabPoint.y()
        #Round OUTWARDS, never towards the middle: a bounding box that is a pixel short of
        #the sprite is a bounding box that lies about what it covers.
        x0, y0 = floor(px + left), floor(py + top)
        x1, y1 = ceil(px + right), ceil(py + bottom)
        return QRect(x0, y0, x1 - x0, y1 - y0)

#-- 拖拽 ------------------------------------------------------------------------------------------------

    def isDragging(self):
        '''当前是否处于拖拽态。

        上半场这个判断是"拿 _dragRadius 是不是 None 当布尔"，因为那个几何量恰好只在
        拖拽期间非空。现在有了明确的标志位，就不再借几何量兼职了。
        '''
        return self.dragging

    def prepareDrag(self, grabGlobalPos):
        '''按下：把抓取点记下来。它就是旋转枢轴。

        窗口在 applyScale 里就已经开到了最坏情况，所以这里**不移动任何东西**——
        这正是"点一下宠物不会跳"的原因。
        '''
        self.grabPoint = QPoint(grabGlobalPos.x() - self.pet.pos().x(),
                                grabGlobalPos.y() - self.pet.pos().y())
        self.dragging = True

    def grabPointInSprite(self):
        '''抓取点在贴图本地坐标里的位置（(0,0) = 贴图左上角）。

        本模式下贴图左上角在窗口的 (spriteInset, spriteInset) 处，所以减掉内缩就换算
        过去了。它决定了她被吊起来时的起始摆角。
        '''
        return QPoint(self.grabPoint.x() - self.spriteInset,
                      self.grabPoint.y() - self.spriteInset)

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
        self.pet.move(int(pivot_x - self.grabPoint.x()),
                      int(pivot_y - self.grabPoint.y()))

    def endDrag(self):
        '''退出拖拽：把窗口挪回它该在的地方，然后自己把拖拽状态清掉。

        没有窗口要回的时候（不在拖拽态）是空操作。
        '''
        if not self.dragging:
            return
        keep_x, keep_y = self._standingPosAfterRelease()
        self.pet.move(keep_x, keep_y)
        self.dragging = False
        self.grabPoint = None

    def spriteOriginInWindow(self):
        '''paintEvent 画旋转贴图时，贴图左上角在窗口里的位置。'''
        return QPoint(self.spriteInset, self.spriteInset)

    def pivotInWindow(self):
        '''paintEvent 的旋转枢轴，窗口坐标。也就是抓取点。'''
        return self.grabPoint

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
        gx = self.grabPoint.x() - self.spriteInset
        gy = self.grabPoint.y() - self.spriteInset
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

    def _standingPosAfterRelease(self):
        '''松手后窗口该在哪，按 (x, y) 返回，窗口坐标。

        窗口在 applyScale 里一次开到了最坏情况，整个拖拽过程都不改尺寸，所以窗口位置
        本来就不用动——这里唯一要做的是：摆动可能把贴图甩出屏幕，按最短距离拉回来。

        （上半场这里还有一个"贴图从拖拽位置回到站立内缩"的补偿量。窗口不再在拖拽时
        改尺寸之后，那个量恒等于 0，已经删掉。）
        '''
        keep_x = self.pet.pos().x()
        keep_y = self.pet.pos().y()
        #The sprite is upright again, so it occupies the plain spriteInset rect.
        W = int(self.pet.ORGINALWIDTH*self.pet._petImageSize)
        H = int(self.pet.ORGINALHEIGHT*self.pet._petImageSize)
        sprite_x = keep_x + self.spriteInset
        sprite_y = keep_y + self.spriteInset
        screen = self.screenRect()
        rightEdge = screen.x() + screen.width()
        bottomEdge = screen.y() + screen.height()
        if sprite_x < screen.left(): keep_x += screen.left() - sprite_x
        elif sprite_x + W > rightEdge: keep_x -= (sprite_x + W) - rightEdge
        if sprite_y < screen.top(): keep_y += screen.top() - sprite_y
        elif sprite_y + H > bottomEdge: keep_y -= (sprite_y + H) - bottomEdge
        return keep_x, keep_y
