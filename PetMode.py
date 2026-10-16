"""窗口模式接口：宠物在屏幕上到底是怎么被"实现"出来的。

两种实现，各占一个文件：

    TrayMode.py        工具栏模式——宠物住在一个跟着它跑的方块窗口里，
                       窗口中心在拖拽时兼任旋转枢轴。
    FullScreenMode.py  全屏模式——窗口固定覆盖主屏、永不移动，
                       宠物在窗口内部移动（将来）。

主流程（DesktopPet）和子系统（游走、对话泡、设置菜单）**只跟这个接口说话**，
所以它们里面没有一处"当前是哪个模式"的判断。要加第三种模式，只加一个文件。

--------------------------------------------------------------------------
两套矩形，各司其职，别混用
--------------------------------------------------------------------------

    petRect()    图片矩形（**未旋转**）。**定位**用它：
                 气泡贴头顶、设置菜单贴边、游走边界、传送落点。
                 拖拽期间也返回它——旋转包围盒会随摆动角度抖，拿它定位气泡会上下抖。

    petBounds()  旋转包围盒。**守卫**用它：
                 拖拽时把整只宠物夹在屏幕内，摆动多厉害都不许露出去。

--------------------------------------------------------------------------
坐标系
--------------------------------------------------------------------------

接口里**不出现"窗口坐标"**。所有位置都指**宠物贴图左上角在屏幕上的坐标**。

原因：工具栏模式下"宠物位置 = 窗口位置 + 内缩"，全屏模式下窗口的 pos() 恒为 (0,0)。
只有"贴图左上角的屏幕坐标"这一个定义在两种模式下都成立。
"""

from abc import ABC, abstractmethod

from PyQt5.QtCore import QPoint, QRect, QSize
from PyQt5.QtWidgets import QApplication


class PetMode(ABC):
    '''宠物在屏幕上的实现方式。子类必须实现全部抽象方法。'''

    def __init__(self, pet):
        '''pet: DesktopPet。

        模式需要读窗口的这些东西：
            ORGINALWIDTH / ORGINALHEIGHT   贴图原始尺寸
            _petImageSize                  贴图缩放
            _dragAngleDeg                  当前绘制角（算包围盒要用）
            petImage / petLabel            贴图和承载它的标签
        也需要调用窗口自己的：move / resize / setGeometry / update。
        跟 _WanderingWork 持有 mainWindow 是同一套写法。
        '''
        self.pet = pet

#-- 生命周期 --------------------------------------------------------------------------------------------

    @abstractmethod
    def configureWindow(self):
        '''按模式决定窗口的 flags 与尺寸。启动时调用一次。

        工具栏：无边框 + 置顶 + (Qt.Window 或 Qt.SubWindow)，尺寸 = 窗口边长
        全屏：  无边框 + 置顶 + Qt.Window，尺寸 = screenRect()
        返回：无
        '''

    @abstractmethod
    def applyScale(self, at=None):
        '''贴图缩放（_petImageSize）变化后的重新布局。

        参数 at: QPoint 或 None。非 None 时表示"顺便把窗口挪到这个屏幕坐标"，
                 供启动时一次调用完成定位+定尺寸，避免"先 resize 后 move"两次
                 SetWindowPos 之间的闪帧。全屏模式忽略它。
        返回：无
        '''

#-- 位置 ------------------------------------------------------------------------------------------------

    @abstractmethod
    def petRect(self):
        '''宠物贴图当前占据的屏幕矩形（**未旋转**）。

        返回：QRect，屏幕坐标。
        这是整个接口里被用得最多的方法——所有"宠物在哪"的定位问题都问它。
        '''

    @abstractmethod
    def placePetAt(self, x, y):
        '''把宠物贴图左上角放到屏幕坐标 (x, y)。

        参数 x, y: int。
        返回：无。

        注意是"移动宠物"而不是"移动窗口"：工具栏模式下二者等价，
        全屏模式下只有前者存在。
        '''

    @abstractmethod
    def randomPetPos(self):
        '''屏幕内一个随机的、保证整只宠物不出屏的落点。

        返回：QPoint，宠物贴图左上角的屏幕坐标。
        '''

#-- 查询 ------------------------------------------------------------------------------------------------

    def screenRect(self):
        '''宠物可用的屏幕区域（只认主屏）。

        返回：QRect。
        两种模式相同，所以这里给了默认实现——替代原先散落 8 处的
        WINDOWWIDTH / WINDOWHEIGHT。
        '''
        return QApplication.primaryScreen().geometry()

    def petSize(self):
        '''贴图当前占据的像素尺寸。

        返回：QSize。两种模式相同，给了默认实现。
        '''
        return QSize(int(self.pet.ORGINALWIDTH * self.pet._petImageSize),
                     int(self.pet.ORGINALHEIGHT * self.pet._petImageSize))

    @abstractmethod
    def petBounds(self):
        '''宠物当前的**旋转包围盒**。

        返回：QRect，屏幕坐标。
        只在"别让宠物跑出屏幕"这类守卫逻辑里用。定位一律用 petRect()。
        '''

#-- 拖拽 ------------------------------------------------------------------------------------------------

    @abstractmethod
    def prepareDrag(self, grabGlobalPos):
        '''鼠标按下：进入拖拽准备态。

        参数 grabGlobalPos: QPoint，光标在屏幕上的位置。
        返回：无。

        不变量：**不得移动宠物或窗口**。这是"点一下宠物不会跳"的保证。
        '''

    @abstractmethod
    def followCursor(self, cursorScreenPos):
        '''拖拽跟随：把旋转枢轴停到光标下，并把整只宠物夹在屏幕内。

        参数 cursorScreenPos: QPoint，光标在屏幕上的位置。
        返回：无。
        '''

    @abstractmethod
    def endDrag(self):
        '''退出拖拽的**几何收尾**。

        返回：无。

        主流程只调这一个方法，不再自行编排"先算位置、再清状态、再移动"。
        工具栏模式在这里做"窗口回到它该在的地方"；全屏模式没有窗口要回，是空实现。
        '''

    @abstractmethod
    def isDragging(self):
        '''当前是否处于「按拖拽方式绘制」的状态。

        返回：bool。
        供 paintEvent / 帧循环 / 退出拖拽三处当开关用，
        取代今天"拿 _dragRadius is not None 当布尔"的做法
        ——_dragRadius 是工具栏模式专有的几何量，不该外泄。
        '''

    @abstractmethod
    def grabPointInSprite(self):
        '''抓取点在**贴图本地坐标**里的位置（(0,0) = 贴图左上角）。

        返回：QPoint。
        拖动时贴图绕抓取点转，所以"抓在她身上哪个部位"决定了起始摆角——抓头顶和
        抓脚底，挂起来的姿态完全不同。这是 sprite 本地量，两种模式下取法不同：
        工具栏模式要从窗口坐标减掉内缩，全屏模式要减掉贴图在窗口里的位置。
        只在拖拽期间才有意义。
        '''

    @abstractmethod
    def spriteOriginInWindow(self):
        '''paintEvent 画旋转贴图时，贴图左上角对应窗口里的哪个点。

        返回：QPoint，**窗口**坐标（这是接口里唯一用窗口坐标的地方，
        因为它直接喂给 QPainter）。
        '''

    @abstractmethod
    def pivotInWindow(self):
        '''paintEvent 的旋转枢轴。

        返回：QPoint，**窗口**坐标。
        '''

#-- 显示 ------------------------------------------------------------------------------------------------

    def setPetVisible(self, visible):
        '''显示 / 隐藏宠物。两种模式行为一致：动窗口透明度。

        参数 visible: bool。
        返回：无。
        '''
        self.pet.setWindowOpacity(1.0 if visible else 0.0)

    def refresh(self, rect=None):
        '''请求重绘。

        参数 rect: QRect 或 None。None = 整窗重绘。
        返回：无。

        工具栏模式整窗重绘无所谓；全屏模式**必须**传 rect 走局部重绘——
        窗口面积从 1242² 变成主屏尺寸（4K 下约 5.4 倍），不局部重绘 CPU 会明显上去。
        '''
        if rect is None:
            self.pet.update()
        else:
            self.pet.update(rect)
