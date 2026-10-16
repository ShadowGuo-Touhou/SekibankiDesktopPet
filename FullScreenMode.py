"""全屏模式的实现。

宠物住在一个**铺满主屏、永不移动**的透明窗口里，她在窗口内部移动。

--------------------------------------------------------------------------
它和工具栏模式的根本差别
--------------------------------------------------------------------------

不是"窗口大不大"，而是**任务栏里有没有一个条目**：

    工具栏模式   Qt.SubWindow   小方块窗口跟着宠物跑   任务栏里没有条目，只剩托盘图标
    全屏模式     Qt.Window      窗口铺满主屏、永不移动  任务栏里长出条目，同时托盘图标还在

录屏软件（OBS 等）能不能把宠物列成窗口捕获源，也是跟着这一条走的：SubWindow 在
Windows 上带 WS_EX_TOOLWINDOW，任务栏和捕获列表里都不会出现。

--------------------------------------------------------------------------
为什么整屏窗口不会挡住桌面
--------------------------------------------------------------------------

不用写代码。Windows 的分层窗口（per-pixel alpha）在命中测试时会跳过 alpha=0 的像素，
所以透明的地方鼠标直接穿过去，点和拖都落在桌面上。

--------------------------------------------------------------------------
坐标系
--------------------------------------------------------------------------

窗口铺满主屏，所以 窗口坐标 = 屏幕坐标 - 主屏原点。对外一律用屏幕坐标，向内换算一次。
"""

import random

from PyQt5.QtCore import QPoint, QRect, Qt

from PetMode import PetMode


class FullScreenMode(PetMode):
    '''全屏模式：窗口钉在主屏上，宠物在窗口内部移动。'''

    def __init__(self, pet):
        super().__init__(pet)
        #贴图左上角，**屏幕坐标**。这是本模式的唯一位置状态。
        self._spritePos = QPoint(0, 0)
        #Whether a drag is under way. isDragging() is the only way anything outside this
        #file asks, so how a drag is represented stays private to the mode.
        self.dragging = False
        #Where on HER the grab landed, in sprite-local coordinates. Constant for the whole
        #drag - it is "which part of her is being held", and that does not change when she
        #is moved. None while not dragging.
        self._grabInSprite = None

#-- 生命周期 --------------------------------------------------------------------------------------------

    def configureWindow(self):
        '''铺满主屏的普通顶层窗口。

        Qt.Window 而不是 SubWindow：任务栏要长出条目，这正是本模式存在的理由。
        无边框、透明、置顶三件事和工具栏模式一致。
        '''
        self.pet.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window)
        self.pet.setGeometry(self.screenRect())
        self._spritePos = self.screenRect().topLeft()

    def applyScale(self, at=None):
        '''只缩贴图，窗口不动。

        参数 at 被忽略：这个模式的窗口从不移动，也就没有"顺便挪到哪"这回事。
        '''
        size = self.petSize()
        self.pet.petImage.setScaledSize(size)
        #The label is exactly sprite-sized here, so it carries the pet rather than
        #containing it the way the tray mode's full-window label does.
        self.pet.petLabel.setAlignment(Qt.AlignCenter)
        self.pet.petLabel.resize(size)
        self._parkLabel()

#-- 位置 ------------------------------------------------------------------------------------------------

    def petRect(self):
        '''宠物贴图当前的屏幕矩形（未旋转）。

        本模式下就是"她自己存的那个位置"，不需要从窗口位置倒推——窗口永远是屏幕本身。
        '''
        return QRect(self._spritePos, self.petSize())

    def placePetAt(self, x, y):
        '''把宠物贴图左上角放到屏幕坐标 (x, y)。

        只重绘**要重绘的那一块**，不是整个屏幕：这个窗口有 4K 那么大，整屏重绘会让
        拖拽明显掉帧。

        拖拽期间那块是**旋转包围盒**，不是未旋转的图片矩形——paintEvent 画的是转过
        角度的贴图，能比图片矩形多伸出去约 90px；按图片矩形失效的话，多出来的那一圈
        永远擦不掉，每一次摆动都会在屏幕上留一道残影。
        '''
        was = self.petBounds() if self.dragging else self.petRect()
        self._spritePos = QPoint(int(x), int(y))
        self._parkLabel()
        now = self.petBounds() if self.dragging else self.petRect()
        self.refresh(was.united(now))

    def randomPetPos(self):
        '''屏幕内一个随机的、保证整只宠物不出屏的落点（宠物左上角）。'''
        screen = self.screenRect()
        size = self.petSize()
        return QPoint(random.randint(screen.left(), screen.right() - size.width()),
                      random.randint(screen.top(), screen.bottom() - size.height()))

#-- 拖拽 ------------------------------------------------------------------------------------------------

    def isDragging(self):
        '''当前是否处于拖拽态。'''
        return self.dragging

    def prepareDrag(self, grabGlobalPos):
        '''按下：记下抓在她身上哪个部位。

        窗口本来就是整个屏幕，**没有任何东西需要移动**——这正是"点一下宠物不会跳"
        的原因。两个屏幕坐标相减，主屏原点自己抵消掉，所以直接就是 sprite 本地坐标。
        '''
        self._grabInSprite = QPoint(grabGlobalPos.x() - self._spritePos.x(),
                                    grabGlobalPos.y() - self._spritePos.y())
        self.dragging = True

    def grabPointInSprite(self):
        '''抓取点在贴图本地坐标里的位置（(0,0) = 贴图左上角）。

        按下时算一次，整个拖拽期间不变——摆角要靠它算，它一动整只宠物就会跟着抖。
        '''
        return QPoint(self._grabInSprite)

    def endDrag(self):
        '''没有窗口要回位——这个模式的窗口从不移动。

        只清掉拖拽状态，并把站立标签放回宠物身上。但**擦干净这件事必须做全**，
        松手这一帧要同时覆盖三块地方，少一块就会在屏幕上留东西：

          1. 松手前画在屏幕上的那块 —— 旋转着画出来的，比图片矩形大；
          2. 标签自己停留的旧位置 —— 拖拽期间 _parkLabel() 是空操作，所以标签一直
             留在**按下之前**那处；调用方随后 show() 会让它在那儿显形一下再被挪走，
             那块地方不擦就会留下一个完整的旧宠物；
          3. 宠物最后站定的位置。

        工具栏模式不需要这些：那边移的是窗口，Windows 会把整个窗口重画。
        '''
        if not self.dragging:
            return
        #All three computed BEFORE the state is cleared, because petBounds() answers
        #differently once the drag is over.
        wasDrawn = self.petBounds()
        labelStale = self._labelScreenRect()
        self.dragging = False
        self._grabInSprite = None
        self._parkLabel()
        self.refresh(wasDrawn.united(labelStale).united(self.petRect()))

    def labelHomeInWindow(self):
        '''站立标签是贴着宠物放的一个贴图大小的方块，所以它就住在宠物左上角。'''
        return self._toWindow(self._spritePos)

    def spriteOriginInWindow(self):
        '''paintEvent 画旋转贴图时，贴图左上角在窗口里的位置。

        本模式里标签和贴图占地完全一样，所以它和 labelHomeInWindow() 是同一个答案；
        工具栏模式下不是（标签铺满窗口、贴图居中在里面），那是两者唯一的区别。
        '''
        return self._toWindow(self._spritePos)

    def pivotInWindow(self):
        '''paintEvent 的旋转枢轴，窗口坐标。

        这里**不能**像工具栏模式那样存一个固定点：窗口钉死在屏幕上，所以要让枢轴
        一直待在光标底下，只能是它跟着宠物在窗口里移动。它就是"宠物左上角 + 抓在
        她身上哪个部位"。

        （工具栏模式恰好相反：窗口跟着宠物跑，于是枢轴在窗口里是个固定的点。同一个
        问题两种相反的答案，这就是它必须是个接口方法的原因。）
        '''
        return self._toWindow(self._spritePos + self._grabInSprite)

#-- 本模式私有 ------------------------------------------------------------------------------------------

    def _screenOrigin(self):
        '''主屏原点。窗口铺满主屏，所以它就是窗口坐标到屏幕坐标的平移量。'''
        return self.screenRect().topLeft()

    def _toWindow(self, screenPoint):
        '''屏幕坐标 -> 窗口坐标。'''
        origin = self._screenOrigin()
        return QPoint(screenPoint.x() - origin.x(), screenPoint.y() - origin.y())

    def _parkLabel(self):
        '''把站立标签停到宠物左上角。拖拽期间标签是藏起来的，不用管。'''
        if not self.dragging:
            self.pet.petLabel.move(self._toWindow(self._spritePos))

    def _labelScreenRect(self):
        '''标签**当前**占据的屏幕矩形，不管它是不是藏着的。

        收尾时要拿它擦掉标签停留过的旧位置——藏起来的控件不会自己告诉 Qt
        "我这里以前有东西"。
        '''
        origin = self._screenOrigin()
        g = self.pet.petLabel.geometry()
        return QRect(g.x() + origin.x(), g.y() + origin.y(), g.width(), g.height())
