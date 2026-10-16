"""工具栏（小窗口）模式的实现。

宠物住在一个边长 side 的方块窗口里，窗口跟着宠物在桌面上移动。窗口中心在拖拽时
同时充当旋转枢轴，所以窗口按「贴图任意角度、任意抓取点都不被裁剪」的最坏情况开
边长（贴图对角线），贴图居中放在里面。

全屏模式是另一套完全不同的做法——窗口固定覆盖主屏、宠物在窗口内部移动——因此它
单独一个文件，不走这里。

这个类通过主窗口引用初始化：它需要读贴图尺寸（ORGINALWIDTH/_petImageSize）、
屏幕尺寸（WINDOWWIDTH/HEIGHT）和标签（petLabel），也需要调用窗口自己的
move/resize/setGeometry。跟 _WanderingWork 持有 mainWindow 是同一套写法。
"""

import random
from math import ceil, hypot, cos, sin, radians

from PyQt5.QtCore import QSize, Qt


class TrayMode:
    '''小窗口模式的窗口几何与位置。'''

    def __init__(self, pet):
        #主窗口。这个模式是"窗口=宠物"的，所以它必须能直接操作那个窗口。
        self.pet = pet
        #窗口边长，以及贴图居中后左右各留的空白。由 applyScale 填。
        self.windowSide = None
        self.spriteInset = None

#-- 布局 ------------------------------------------------------------------------------------------------

    def applyScale(self, at=None):
        '''按当前 _petImageSize 重算窗口尺寸，并重排标签。

        窗口要够大以容纳任意抓取点、任意角度的旋转贴图：窗口中心就是旋转枢轴，
        所以窗口只需够到最远的角，也就是对角线。一次到位意味着拖拽过程中永远
        不需要再改窗口尺寸。
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

    def moveWindow(self, x, y):
        '''本模式下唯一移动窗口的出口。

        小窗口模式里"宠物在屏幕上的位置"就等于"窗口的位置"，所以移动宠物就是移动
        窗口。全屏模式下这一条不成立，那时会换成移动窗口内部的贴图。
        '''
        self.pet.move(int(x), int(y))

    def randomPos(self):
        #Choose a random point on the screen where desktop pet won't go off screen
        petSize = self.pet.size()
        return (random.randint(0, self.pet.WINDOWWIDTH-petSize.width()),
                random.randint(0, self.pet.WINDOWHEIGHT-petSize.height()))

    def teleport(self):
        x, y = self.randomPos()
        self.moveWindow(x, y)

#-- 拖拽 ------------------------------------------------------------------------------------------------

    def beginDrag(self, dragPos):
        '''进入拖拽态。

        窗口在 applyScale 里就已经开到了最坏情况，所以这里只是把抓取点记成枢轴，
        窗口和贴图一步都不动——这正是"点一下不会跳"的原因。
        '''
        self.pet._dragRadius = self.windowSide//2
        self.pet._spriteOrigin = (self.spriteInset, self.spriteInset)
        self.pet._pivotOffset = dragPos

    def spriteExtents(self):
        '''贴图相对「窗口中心」伸出多少：(left, top, right, bottom)。

        站立时就是半个贴图。拖拽时窗口中心就是枢轴、宠物以某个角度挂在它上面，
        所以把四个角按绘制角旋转后取包围盒。需要宠物真实轮廓的调用方（边缘夹取、
        对话泡定位）都用这个，谁都不用假设贴图是正的。
        '''
        W = int(self.pet.ORGINALWIDTH*self.pet._petImageSize)
        H = int(self.pet.ORGINALHEIGHT*self.pet._petImageSize)
        if self.pet._dragRadius is None:
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

    def parkPivotAt(self, cursorPos):
        '''把枢轴停在光标下面，并把整只宠物夹在屏幕内。

        抓取点在窗口坐标里就是枢轴，所以把窗口中心停到光标上，任何旋转角下被抓的
        那一块都还在鼠标底下。这就是取代旧 _drag_pos + "+15" 锚点修正的东西。
        '''
        #The window centre is the pivot, so spriteExtents hands back the bounding box of
        #the rotated sprite around it; clamping the pivot by those four reach values keeps
        #the whole pet inside whatever angle it is hanging at.
        left, top, right, bottom = self.spriteExtents()
        pivot_x = cursorPos.x()
        pivot_y = cursorPos.y()
        if pivot_x < -left: pivot_x = -left
        elif pivot_x > self.pet.WINDOWWIDTH - right: pivot_x = self.pet.WINDOWWIDTH - right
        if pivot_y < -top: pivot_y = -top
        elif pivot_y > self.pet.WINDOWHEIGHT - bottom: pivot_y = self.pet.WINDOWHEIGHT - bottom
        self.moveWindow(pivot_x - self.pet._pivotOffset.x(),
                        pivot_y - self.pet._pivotOffset.y())

    def dragExitPos(self):
        '''退出拖拽时窗口该回到哪里，按 (x, y) 返回，由调用方决定何时真正移动。

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
        if sprite_x < 0: keep_x -= sprite_x
        elif sprite_x + W > self.pet.WINDOWWIDTH: keep_x -= (sprite_x + W) - self.pet.WINDOWWIDTH
        if sprite_y < 0: keep_y -= sprite_y
        elif sprite_y + H > self.pet.WINDOWHEIGHT: keep_y -= (sprite_y + H) - self.pet.WINDOWHEIGHT
        return keep_x, keep_y
