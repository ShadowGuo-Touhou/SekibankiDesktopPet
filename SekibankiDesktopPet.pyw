import os , sys, random, time
from PyQt5.QtCore import QObject
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import *
from SettingBox import SettingMenu
from math import pi, atan,atan2, cos, sin, radians
#Inspired by: https://zhuanlan.zhihu.com/p/521580516

class DesktopPet(QWidget):
    #initialization process
    def __init__(self, parent=None, **kwargs):
        super().__init__()
        #initialize setting menu and grab the config list
        self._initSettingMenu()
        #initialize the window
        self._init()
        #initialize and show pet image
        self._initPetImage()
        #initialize the tray icon for pet
        self._initTrayIcon()
        #initialize the standby actions
        self._initStandBy()
        #initialize dialog functions
        self._initDialog()
        #Display self (this is different from opacity)
        self.show()

#Initialization------------------------------------------------------------------------------------------
        
    def _init(self):
        #FramelessWindowHint: create a frameless window
        #WindowStaysOnTopHint: keep window on top
        #SubWIndow: keep the window a subwindow regardless of the existance of parent window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        # self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        #Don't fill window with background color
        self.setAutoFillBackground(False)
        #Set window transparent
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        #refresh window
        self.update()

        #List of conditions and pre-defined variables
        #the facing state of pet: 0 is facing right, 1 is facing left
        self.__facingDirection = None
        #The array containing the states for desktopPet
        self.normalStates = [r"assets/Sprite/normalRIght.gif", r"assets/Sprite/normalLeft.gif"]
        self.dragState = [r"assets/Sprite/dragRight.png", r"assets/Sprite/dragLeft.png"]
        #Condition to see if the pet is talking
        self._speechBubbleCondition = False
        self._draggable = True
        #The scale of gif
        self._petImageSize = 0.8
        #Constants
        self.WINDOWWIDTH = QApplication.primaryScreen().size().width()
        self.WINDOWHEIGHT = QApplication.primaryScreen().size().height()
        self.ORGINALWIDTH = 549
        self.ORGINALHEIGHT = 549
        self.MARGIN = 250
        #the configuration
        self.SETTING = self._settingMenu.getConfig()
        self._amplifier = self.SETTING['amplifier']

    def _initTrayIcon(self):
        #import prepared trayicon image
        iconImage = os.path.join('assets/icon.ico')
        #Create the tray icon
        self._tray_menu = QSystemTrayIcon(self)
        #set the icon image
        self._tray_menu.setIcon(QIcon(iconImage))

        #Create the tray icon menu for tray icon
        self._tray_icon_menu = QMenu(self)
        #create a quit action for the pet
        quit_action = QAction("Exit", self, triggered=self.quit)
        #create a display or hide the pet
        display_action = QAction("Display/Hide", self, triggered=self.display)
        #Add two events to the menu
        bigger_action = QAction("Bigger?", self, triggered = self._increaseSize)
        smaller_action = QAction("Smaller?", self, triggered=self._decreaseSize)
        
        self._tray_icon_menu.addAction(display_action)
        self._tray_icon_menu.addAction(bigger_action)
        self._tray_icon_menu.addAction(smaller_action)
        # self._tray_icon_menu.addAction(teleport)
        self._tray_icon_menu.addAction(quit_action)

        self._tray_menu.setContextMenu(self._tray_icon_menu)
        self._tray_menu.show()

    #create a timer that reset its interval upon triggered
    class SpeechBubbleTimer(QTimer):
        timeout = pyqtSignal(str)
        def __init__(self, parent: QObject | None, id = 'default', start = 2, end = 10, color='white', fontcolor='black') -> None:
            super().__init__(parent)
            self.startI = start * 1000
            self.endI = end * 1000
            self.id = id
            self.color = color
            self.fontcolor = fontcolor
            self.setInterval(random.randint(self.startI, self.endI))

        def timerEvent(self, a0: QTimerEvent | None) -> None:
            self.setInterval(random.randint(self.startI, self.endI))
            self.timeout.emit(self.id)
            # print(f'{self.id} timeout')
            return super().timerEvent(a0)
        
        def __str__(self) -> str:
            
            return self.id

    #Second version of dialog
    def _initDialog(self):
        for dialog in self.DIALOGS.values():
            if dialog['id'] == 'clickDialog':
                continue
            if not dialog['dialog']:
                continue
            timer = self.SpeechBubbleTimer(self, id=dialog['id'], start = dialog['start'], end = dialog['end'], color = dialog['color'])
            timer.timeout.connect(lambda id: self._speechBubbling(id = id))
            self._standByTimers[dialog['id']] = timer
        
    
    #Trigger click dialog
    def _triggerClickDialog(self):
        if self._clickDialogExist == True and self.DIALOGS['clickDialog']['dialog']:
            self._speechBubbling(id = 'clickDialog')
        

#The menu display----------------------------------------------------------------------------------------
    
    #initialize settings
    def _initSettingMenu(self):
        self._settingMenu = SettingMenu()
        self._settingMenu.finished.connect(self._SettingMenuClose)
        self._settingMenu.warning.connect(lambda x: self._speechBubbling(x))
        self.DIALOGS = self._settingMenu.getDialog()
        if 'clickDialog' in self.DIALOGS:
            self._clickDialogExist = True
        else: self._clickDialogExist = False
        self._settingMenu.dialogChanged.connect(lambda id: self._dialogChanged(id=id))


    def _SettingMenuOpen(self):
        self._quitStandbyPhase()
        #move the menu
        self._settingMenuMove()
        #Show
        self._settingMenu.show()
        #forbid user from dragging desktop pet while menu is on
        self._draggable = False
    
    def _SettingMenuClose(self):
        self._beginStandbyPhase()
        #reactive dragging after user close menu
        self._draggable = True

    #Adjust the position when opening the menu
    def _settingMenuMove(self):
        currPos = self.pos()
        selfSize = self.size()
        menuSize = self._settingMenu.size()
        #put x to the right of the desktop pet
        x = currPos.x() + selfSize.width() - self.MARGIN//2 if self.WINDOWWIDTH - currPos.x() - selfSize.width() + self.MARGIN//2> menuSize.width() else currPos.x() - menuSize.width() + self.MARGIN//2
        y = currPos.y() + selfSize.height()//2 - menuSize.height()//2
        if y + menuSize.height() > self.WINDOWHEIGHT:
            y = self.WINDOWHEIGHT - menuSize.height()
            return self._settingMenu.move(x,y)
        if y < 0: 
            y = 0
        self._settingMenu.move(x,y)

    def _dialogChanged(self, id):
        if id in self._standByTimers.keys():
            self._standByTimers.pop(id).deleteLater()
        self.DIALOGS = self._settingMenu.getDialog()
        dialog = self.DIALOGS[id]
        if not dialog['dialog'] or id == 'clickDialog':
            return
        timer = self.SpeechBubbleTimer(self, id=dialog['id'], start = dialog['start'], end = dialog['end'], color = dialog['color'])
        timer.timeout.connect(lambda id: self._speechBubbling(id = id))
        self._standByTimers[id] = timer
    


#Pet ImageDisplay----------------------------------------------------------------------------------------

    def _initPetImage(self):
        #create a label that stores the image of pet
        self.petLabel = QLabel(self)
        

        #randomly choose a starting facing direction for pet
        self._changeFacingDirection(random.randint(0,1))

        #go to a random position on the desktop
        randomPos = self._randomPos()
        self.move(randomPos[0], randomPos[1])

#Pet Standby Actions-------------------------------------------------------------------------------------

    def _initStandBy(self):
        #Create a timer for wandering function, where the pet moves around the desktop
        self._wanderingTimer = QTimer(self)
        #once the timer time out, trigger _wandering function
        self._wanderingTimer.timeout.connect(self._wandering)
        #start the timer
        self._wanderIngTimerReset()

        #Create a container for timer
        self._standByTimers = {} 
        self._standByTimers['wanderingTimer'] = self._wanderingTimer

    #the function for wandering, becauses it involves a loop that can't be put in the main loop, we need another thread for it
    def _wandering(self):
        #create a thread to run subprocess
        self._wanderingThread = QThread(parent=self)
        #create the wandering class and pass in self(DesktopPet)
        self._wanderingWork = self._WanderingWork(self, 300*(self._petImageSize*2-1))
        #Add wandering class to thread to be run
        self._wanderingWork.moveToThread(self._wanderingThread)
        #Connect run signal of wandering thread to the start of run function
        self._wanderingThread.started.connect(self._wanderingWork.run)
        #quit the thread if run finished
        self._wanderingWork.finished.connect(self._wanderingThread.quit)
        #delete both the thread and class from memory upon finished
        self._wanderingWork.finished.connect(self._wanderingWork.deleteLater)
        self._wanderingThread.finished.connect(self._wanderingThread.deleteLater)

        #Move desktop Pet upon receiving the signal date
        self._wanderingWork.moveSignal.connect(lambda coor: self.move(coor[0], coor[1]))

        #Change the facing of pet upon reciving the facing data
        self._wanderingWork.changeFacingDirectionSignal.connect(lambda facing: self._changeFacingDirection(facing))

        #Reset the time interval of wanderingTimer:
        self._wanderingThread.finished.connect(self._wanderIngTimerReset)
        
        #Start the thread 
        self._wanderingThread.start()

        
    #create a class that inherites QObject so QThread recognizes and runs it
    class _WanderingWork(QObject):
        #Create a signal to indicate the end of the thread process
        finished = pyqtSignal()
        moveSignal = pyqtSignal(list)
        changeFacingDirectionSignal = pyqtSignal(int)

        def __init__(self, mw, mr = 300):
            #initialize super class
            super().__init__()
            #pass in the DesktopPet class so we can call on its move function
            self.mainWindow = mw
            self.mr = int(mr)
            self.margin = int(mw.MARGIN*mw._petImageSize/2)

        def run(self):
            #The range of movement distance is movementrange "mr" pixel to both side
            #Get the current position
            currentPos = self.mainWindow.pos()
            screenSize = QApplication.primaryScreen().size()
            #random a destine position with random.randint(a,b). a and b equals to either 0 or maxscreen (width/height  - half of the desktop pet size) if out of screen. (that's some long ass code!)
            xStart = currentPos.x() - self.mr + self.margin if currentPos.x() > self.mr - self.margin else 0 - self.margin
            xEnd = currentPos.x() - self.margin + self.mr if screenSize.width() > currentPos.x() + self.mr + self.mainWindow.size().width() - self.margin else screenSize.width()-self.mainWindow.size().width() + self.margin
            xStart = abs(xStart)
            xEnd = abs(xEnd)
            xDestiny = random.randint(min(xStart,xEnd),max(xStart,xEnd))
            
            yStart= currentPos.y() + self.margin - self.mr if currentPos.y() > self.mr - self.margin else 0 - self.margin
            yEnd = currentPos.y() + self.mr - self.margin if screenSize.height()> currentPos.y() + self.mr + self.mainWindow.size().height() - self.margin else screenSize.height()-self.mainWindow.size().height() + self.margin
            yStart = abs(yStart)
            yEnd = abs(yEnd)
            yDestiny = random.randint(min(yStart,yEnd),max(yStart,yEnd))
            #calculates the difference between current position and destiny. For the sake of memory, I'll reuse variables. This step converts the absolute position on a screen to a relative position to the current position.
            #This is esscentially a substraction of two R2 vectors.
            xDestiny = xDestiny - currentPos.x()
            yDestiny = yDestiny - currentPos.y()

            #To create a smooth, diagonal movement from current position to destiny position, the change is x, y coordination must have a ratio, which is the slop formula. 
            #Sadly, the pixel can't be decimal (float). the change has to be in integers (int). We need to divide out the greatest common factor from the x to y ration. Considering some extreme cases of two prime numbers (11 to 17), let's change the unit position to zero. 
            #Now they at least have a 10 for greatest common factor/greatest common divisor
            xDestiny = xDestiny//10 * 10
            yDestiny = yDestiny//10 * 10
            #Notice that xDestiny and yDestiny can be negative. Since gcf doesn't care about signs, it doesn't matter... why did I even write this down?
            gcf = abs(self.gcd(xDestiny, yDestiny))
            if gcf == 0: gcf =1

            #Create the change value. Since I'll reuse it multiple times, create two variables for them.
            delatX = xDestiny//gcf
            delatY = yDestiny//gcf

            #change the facing direction of desktop pet when moving
            #xDestiny < 0 means desktop is moving to the left, vice versa
            self.changeFacingDirectionSignal.emit(1 if xDestiny <0 else 0)

            #apply the change. 
            x = self.mainWindow.pos().x()
            y = self.mainWindow.pos().y()
            for i in range(gcf):
                # send back the coordinate in a list with vector
                self.moveSignal.emit([x + delatX*i, y + delatY*i])
                #30 fps
                time.sleep(1/30)

            #Emit finished signal so main thread can kill the subtread
            self.finished.emit()

        #a quick function for gcd.
        def gcd(self, a, b):
            while b:
                a, b = b, a%b
            return a

    def _wanderIngTimerReset(self):
        self._wanderingTimer.start(random.randint(self.SETTING['start'], self.SETTING['end'])*1000)
    
    def _speechBubbling(self, text=None, id = None):
        #Don't creat new window if there is one already
        if self._speechBubbleCondition == True:
            return

        #Determine what type of speech bubble to display
        #If entered text, its a system text, default some attribute
        if text:
            self._speechBubble = self._SpeechBubbleClass(self._petImageSize, opacity=self.SETTING['speechBubbleOpacity'])
            self._speechBubbleWork = self._SpeechBubbleWork(self, self._speechBubble, 3)
            self._speechBubble.setText(text)
        else:
            self._speechBubble = self._SpeechBubbleClass(self._petImageSize, color = self.DIALOGS[id]['color'], opacity=self.SETTING['speechBubbleOpacity'], fontColor=self.DIALOGS[id]['textColor'])
            self._speechBubbleWork = self._SpeechBubbleWork(self, self._speechBubble, self.DIALOGS[id]['time'])
            self._speechBubble.setText(random.choice(self.DIALOGS[id]['dialog']))


        #Create a thread for speechbubble
        self._speechBubbleThread = QThread(parent=self)
        #move to thread
        self._speechBubbleWork.moveToThread(self._speechBubbleThread)
        #connect the start of thread to speechBubbleWork's run function
        self._speechBubbleThread.started.connect(self._speechBubbleWork.run)
        self._speechBubbleConditionChange()
        self._speechBubbleThread.finished.connect(self._speechBubbleThread.deleteLater)
        self._speechBubbleWork.finished.connect(self._speechBubbleThread.quit)
        self._speechBubbleWork.finished.connect(self._speechBubbleWork.deleteLater)
        self._speechBubbleWork.finished.connect(self._speechBubble.deleteLater)
        self._speechBubbleWork.finished.connect(self._speechBubbleConditionChange)
        self._speechBubbleWork.move.connect(lambda coor: self._speechBubble.move(coor[0], coor[1]))

        self._speechBubbleThread.start()
        self._speechBubble.show()


    #Speech bubble functions
    #Speech bubble is displayed above Desktop pet for a certain period of time when triggered.
    #Define a class for SpeechBubble for abstraction/code encapsulation
    class _SpeechBubbleClass(QMainWindow):
        def __init__(self, scaler = 1, color = 'white', opacity = 1, fontColor = 'black'):
            super().__init__()
            #basic settings
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setFixedHeight(int(100*scaler))
            #Text display, dynamically adjust to fix the size of desktop pet
            self._textBox = QLabel(self)
            self._textBox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._textBox.setMargin(int(20*scaler))
            color = QColor(color).getRgb()
            colorModified = (color[0],color[1],color[2], opacity)
            self._textBox.setStyleSheet(f"border-style: groove; border-width: {int(5*scaler)}px; border-radius: 20px; background-color: rgba{colorModified}; font-size: {int(30*scaler)}px; color:{fontColor} ")

            # font = QFont('Saitamaar.ttf')
            # self._textBox.setFont(font)
            #Put Qlabel into the speech bubble
            self.setCentralWidget(self._textBox)
            self._textBox.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            #Set text for the label
        def setText(self, a0: str | None) -> None:
            self._textBox.setText(a0)
            #adjust the size of the Mainwindow after QLabel expanded by text
            self.adjustSize()
        
        def width(self):
            return self._textBox.size().width()
        
        def height(self):
            return self._textBox.size().height()

    #Create the thread that's going to carry out the movement of the speech bubble
    class _SpeechBubbleWork(QObject):
        finished = pyqtSignal() 
        #This signal returns the coor speech bubble moves to
        move = pyqtSignal(list) 

        def __init__(self, mw, sb, T2T):
            super().__init__()
            #Desktop pet
            self.mainWindow = mw
            #the speech bubble
            self.speechBubble = sb
            #the display period of speech bubble
            self.time2Live = T2T
            
        def run(self):
            #Get the size of the screen
            screenWidth = QDesktopWidget().screenGeometry(0).width()
            selfWidth = self.speechBubble.width()
            selfHight = self.speechBubble.height()
            for i in range( int(self.time2Live*30) ):
                mainPos = self.mainWindow.pos()
                mainWidth = self.mainWindow.size().width()
                mainHeight = self.mainWindow.size().height()
                xPos = mainPos.x() + mainWidth//2 - selfWidth//2
                yPos = mainPos.y() - selfHight + self.mainWindow.MARGIN*self.mainWindow._petImageSize//2

                #prevent the speech bubble from going off screen
                if xPos < 0: xPos = 0
                elif xPos+selfWidth>screenWidth: xPos = screenWidth - selfWidth
                #If the space above desktop isn't enought, move the speech bubble down
                if yPos < 0: yPos = mainPos.y() + mainHeight - self.mainWindow.MARGIN*self.mainWindow._petImageSize//2

                self.move.emit([int(xPos), int(yPos)])
                #FPS
                time.sleep(1/30)
            self.finished.emit()
    
    def _speechBubbleConditionChange(self):
        self._speechBubbleCondition = not self._speechBubbleCondition 
    
#-Mouse Interaction--------------------------------------------------------------------------------------

    def mousePressEvent(self, event):
        #Quite standby phase, lest undetermined behavior
        self._quitStandbyPhase()
        #Flag for pet transformation
        self._rotationMatrixTranslate = True

        #Enter drag event if mouse pressed is left button
        if event.button() == Qt.LeftButton and self._draggable:
            self._draging = True
            #adjust anchor of movement position
            self._drag_pos = event.globalPos() - self.pos()
            self._previous_drag_pos = event.globalPos()
        else:
            self._draging = False
            self._SettingMenuOpen()

        self._triggerClickDialog()



        event.accept()
        #Change the cursor type while draging
        self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseMoveEvent(self, event):
        # If left mouse button is pressed and pet is in drag state
        if Qt.LeftButton and self._draging:
            #call on move function defined below
            self._petDragMovement(event.globalPos())
        event.accept()

    def mouseReleaseEvent(self, event):
        #resume standby phase
        self._changeFacingDirection(self._facingDirection)
        self._beginStandbyPhase()
        self._draging = False
        self.setCursor(QCursor(Qt.ArrowCursor))

#Minor Functions-----------------------------------------------------------------------------------------
        
    #Quit the desktop pet
    def quit(self):
        self.close()
        sys.exit()

    #Display or hide the desktop pet depending on the current state
    def display(self):
            self.setWindowOpacity(not self.windowOpacity())
            if self.windowOpacity == 0:
                self._quitStandbyPhase()
            else:
                self._beginStandbyPhase()

    #Choose a random point on the screen where desktop pet won't go off screen
    def _randomPos(self) -> int:
        petSize = self.size()
        return random.randint(0, self.WINDOWWIDTH-petSize.width()), random.randint(0, self.WINDOWHEIGHT-petSize.height())
    
    #This function decides the type of movement desktoppet is experiencing.
    def _petDragMovement(self, eventPos:int, ) -> None:
        #decide the current facing direction by mius
        facingDirection = self._previous_drag_pos.x() - eventPos.x()
        #Grab the change in position
        dx = abs(facingDirection)
        #adjust the facingDirection based on the sign of difference
        self._facingDirection = 1 if facingDirection < 0 else 0



        #Margin
        margin = self.MARGIN * self._petImageSize //2

        #update previous drag pos
        self._previous_drag_pos = eventPos
        #call the drag movement angle for the drag physic effect
        self._changeDragAngle(dx, eventPos)
        destination = eventPos-self._drag_pos
        xPos = destination.x() 
        yPos = destination.y()
        if xPos < 0 - margin: xPos = 0 - margin
        elif xPos > self.WINDOWWIDTH - self.width() + margin: xPos = self.WINDOWWIDTH - self.width() + margin

        if yPos < 0 - margin: yPos = 0 - margin
        elif yPos > self.WINDOWHEIGHT - self.height() + margin: yPos = self.WINDOWHEIGHT - self.height() + margin

        self.move(int(xPos), int(yPos))

    #Standby phase is when there isn't any user interaction with desktop pet. 
    #During standby phase, QTimers will kick for standby behaviors and speech bubbles, but they might leads to undertermined behavior if executed during user interactions. So, they have to paused.
    def _quitStandbyPhase(self):
        for Timer in self._standByTimers.values():
            Timer.stop()

    #resume standby phase
    def _beginStandbyPhase(self):
        for Timer in self._standByTimers.values():
            Timer.start()

    #change facing direction
    def _changeFacingDirection(self, facingDirection):
        #"self.normalStates" is an array where 0 is the gif of facing right, 1 is the gif of facing left
        self._facingDirection = facingDirection
        #load the gif into petImage
        self.petImage = QMovie(self.normalStates[self._facingDirection])
        #load petImage into petLabel
        self.petLabel.setMovie(self.petImage)
        #call resize to rescale gif if apply
        self._resize()
        #begin to play the gif
        self.petImage.start()

    def _changeDragAngle(self, dx, eventPos):
        #if the greatest dx can be is 50
        
        #dx is the change in position, i.e.velocity of the cursor
        #Use equation Δθ = (wi)t + (1/2)(a)(t**2) to derive the angle change
        t = 1
        a = -0.5
        dTheta = dx*t*self._amplifier + 0.5*a*(t)**2

        #Change rotation direction based of facingDirection
        dTheta = -dTheta if self._facingDirection == 0 else dTheta
        
    #simulate the physic effect of pet rotated due to gravity, it is aorund the piovt (where user clicks)
    #Since the grab position doesn't change during the drag, we only need it to run once
        if self._rotationMatrixTranslate:
            #Find the difference in Y from the center of the pet
            ydiff = self.size().height()//2- self._drag_pos.y()
            #Find the difference in X from the center of the pet
            xdiff = -(self.size().width()//2 - self._drag_pos.x())
            #Prevent divided by 0 error
            if xdiff == 0: xdiff = 1
            grabAngle = atan(ydiff/xdiff) * (180/pi)
            self.grabAngle = grabAngle-90 if xdiff>0 else grabAngle+90
            # grabAngle= self.grabAngle if self.grabAngle>0 else grabAngle+90
            # # grabAngle = -60
            # # self.grabAngle = 300

            # angle = radians(grabAngle)

            # shiftDistance = QPoint(self.size().width()//2, self.size().height()//2) + self.pos()
            # # eventPos = QPoint(731, 500)

            # clickPointT = eventPos - shiftDistance
            # topLeftT = self.pos()-shiftDistance
            

            # #Finding the position of the rotated points.
            # # the rotation is accompolished by the following matrix operation:
            # # |x| \/ |cosθ -sinθ|
            # # |y| /\ |sinθ  cosθ|
            # # x = xcosθ - ysinθ
            # # y = xsinθ + ycosθ

            # #CLickpoint rotated
            # xPrime = clickPointT.x()*cos(angle) - clickPointT.y()*sin(angle)
            # yPrime = clickPointT.x()*sin(angle) + clickPointT.x()*cos(angle)
            # clickPointTR = QPoint(int(xPrime), int(yPrime))
        

            # #Topleft rotated
            # xPrime = topLeftT.x()*cos(angle) - topLeftT.y()*sin(angle)
            # yPrime = topLeftT.x()*sin(angle) + topLeftT.x()*cos(angle)
            # topLeftTR = QPoint(int(xPrime), int(yPrime))

            # #Find the distance from topleft rotated to it's origin
            # shiftDistance2 = eventPos - clickPointTR 
            # topLeftTT = topLeftT+shiftDistance2

            # print(f"""
            #     Topleft = {self.pos().x(), self.pos().y()}
            #     Click position = {eventPos.x(), eventPos.y()}
            #     Shift distance = {shiftDistance.x(), shiftDistance.y()}

            #     Topleft translated = {topLeftT.x(), topLeftT.y()}
            #     Click position translated = {clickPointT.x(), clickPointT.y()}

            #     Angle: rad={angle} deg={grabAngle} self.grabAnge={self.grabAngle}
            #     cos(Angle) = {cos(angle)}, sin(Angle) = {sin(angle)}
            #     Topleft rotated = {topLeftTR.x(), topLeftTR.y()}
            #     Click position rotated = {clickPointTR.x(), clickPointTR.y()}
            #     Shift distance2 = {shiftDistance2.x(), shiftDistance2.y()}
            #     Topleft translated again = {topLeftTT.x(), topLeftTT.y()}

            # """)

            #Map the drag_pos to the correspoinding poin in the rotated image. 
            #First set the center of the rotation to the center of the image, so the mapped point doesn't rotates to another quadrant.
            #Rotate by the same angle we rotate image. #Update: somehow there is a discrepency if we rotate by the same angle. By adding 15 to the rotation angle solves it...no idea why.
            #translated the center back to topleft
            transformer = QTransform().translate(self.size().width()/2, self.size().height()/2).rotate(self.grabAngle+15).translate(-self.size().width()/2, -self.size().height()/2)
            new_drag_pos = transformer.map(self._drag_pos)

            # self.eventPosL = QLabel()
            # self.eventPosL.setText("EventPose")
            # self.eventPosL.move(eventPos)
            # self.eventPosL.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
            # self.eventPosL.show()


            # self.dragPosL = QLabel()
            # self.dragPosL.setText("MappedPoint")
            # self.dragPosL.move(self.pos()+new_drag_pos)
            # self.dragPosL.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
            # self.dragPosL.show()

            # moveDistance = (eventPos-self.pos()-new_drag_pos)
            # print(self.grabAngle)
            # self.move(self.pos()+moveDistance)

            #update the coordinate of drag pos
            self._drag_pos = new_drag_pos
            self._rotationMatrixTranslate = False

        #Grab the sprite corresponding to the facing direction and then scale it according to the scaler
        banki = QPixmap(self.dragState[self._facingDirection]).scaled(int(self.ORGINALWIDTH*self._petImageSize), int(self.ORGINALHEIGHT*self._petImageSize))
        
        
        transformer = QTransform().rotate(self.grabAngle).rotate(dTheta)
        self.petLabel.setPixmap(banki.transformed(transformer))
        # self.petLabel.setPixmap(banki)


    def _resize(self):
        #get the width&height after resize
        newWidth = int(self.ORGINALWIDTH*self._petImageSize)
        newHeight = int(self.ORGINALHEIGHT*self._petImageSize)
        #rescale petImage with it.
        self.petImage.setScaledSize(QSize(newWidth, newHeight))
        #Resize the window and the label holding gif        
        self.resize(newWidth+self.MARGIN, newHeight+self.MARGIN)
        self.petLabel.resize(newWidth+self.MARGIN, newHeight+self.MARGIN)
        self.petLabel.move(self.MARGIN//2, 0)
        
        

    #Increase the size of Desktop pet
    def _increaseSize(self):
        #increase the size scaler by 0.1
        if self._petImageSize <= 2:
            self._petImageSize += 0.1
            self._resize()
        

    #Decrease the size of Desktop pet
    def _decreaseSize(self):
        #decrease the size scaler by 0.1
        if self._petImageSize >= 0.3:
            self._petImageSize -= 0.1
            self._resize()

    def _teleport(self):
        l = self._randomPos()
        self.move(l[0], l[1])
        
        

if __name__ == '__main__':
    #initialize
    app = QApplication(sys.argv)
    #Produce an error log on tailed starts
    # try:
    #     pet = DesktopPet()
    # except Exception as e:
    #     crash=["Error on line {}".format(sys.exc_info()[-1].tb_lineno),"\n",e]
    #     timeX=str(time.time())
    #     with open("ErrorLog"+timeX+".txt","w+") as crashLog:
    #         for i in crash:
    #             i=str(i)
    #             crashLog.write(i)
    pet = DesktopPet()
    sys.exit(app.exec_())