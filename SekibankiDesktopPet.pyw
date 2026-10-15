import os , sys, random, time
from PyQt5.QtCore import QObject
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import *
from SettingBox import SettingMenu
from math import pi, atan,atan2, cos, sin, radians, hypot, ceil
from PhysicalModule import DragSwing
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

        #-- assets ------------------------------------------------------------------
        #Pictures the pet uses, indexed by facing direction (0 = right, 1 = left)
        self.normalStates = [r"assets/Sprite/normalRIght.gif", r"assets/Sprite/normalLeft.gif"]
        self.dragState = [r"assets/Sprite/dragRight.png", r"assets/Sprite/dragLeft.png"]
        #The label that actually draws the pet, filled in by _initPetImage
        self.petLabel = None
        #Standing animation cache, one QMovie per direction, built further down.
        #Creating a QMovie restarts its animation from frame 0, which made the pet twitch on
        #every click, so each movie is built once and kept alive.
        self._petImages = []
        #The movie currently shown. It points at one of _petImages and only exists once a
        #direction has been chosen, so treat it as optional.
        self.petImage = None

        #-- geometry constants ------------------------------------------------------
        self.WINDOWWIDTH = QApplication.primaryScreen().size().width()
        self.WINDOWHEIGHT = QApplication.primaryScreen().size().height()
        self.ORGINALWIDTH = 549
        self.ORGINALHEIGHT = 549
        #Blank border kept around the pet so a rotated or enlarged sprite is not clipped
        self.MARGIN = 250
        #Scale of the standing gif and of the drag sprite
        self._petImageSize = 0.8
        #The window is sized once for the worst case - the sprite at any rotation about any
        #grab point - and the sprite sits dead centre in it. Both are derived in _resize().
        #Sizing it up front is what lets a drag only ever MOVE the window: a size change is a
        #separate SetWindowPos from a move and Windows presents the frame in between, which is
        #the flash you see on every click.
        self._windowSide = None
        self._spriteInset = None
        #Where the grab point sits inside the window, i.e. the rotation pivot. The pivot does
        #NOT have to be the window centre: keeping it wherever it already is means pressing
        #down never has to move the window, which is what made the pet appear to jump.
        self._pivotOffset = None

        #-- interaction state -------------------------------------------------------
        #0 is facing right, 1 is facing left. It only carries a value during a drag.
        self._facingDirection = 0
        #Left button is currently held on the pet
        self._draging = False
        #The pet was actually moved since the button went down; a plain click never drags
        self._dragged = False
        #Where the pet was grabbed, in window coordinates. _changeDragAngle rewrites this once
        #per drag so the grabbed point follows the cursor while the sprite rotates.
        self._drag_pos = None
        #Cursor position of the previous move event, used to derive the drag speed
        self._previous_drag_pos = None
        #Whether the pivot angle of the current grab has been worked out yet
        self._rotationMatrixTranslate = True
        #Angle the pet hangs by, derived from where it was grabbed. Created on the first drag.
        self.grabAngle = None
        #Closed while the setting menu is open, so dragging cannot fight the menu
        self._draggable = True

        #-- drag window geometry ----------------------------------------------------
        #While dragging, the window is a square of side 2*_dragRadius with the grabbed
        #point sitting exactly at its centre. That makes the window centre the rotation
        #pivot, so the sprite can swing to any angle without being clipped.
        #None means "not dragging".
        self._dragRadius = None
        #Top-left corner of the sprite inside the drag window
        self._spriteOrigin = None
        #Angle the drag sprite is drawn at, i.e. grabAngle + the pendulum's theta
        self._dragAngleDeg = 0.0
        #Scaled drag sprites keyed by (direction, width, height), built once and reused
        self._dragPixmaps = {}
        #Whether we currently hold an explicit mouse grab (see mousePressEvent)
        self._mouseGrabbed = False

        #-- Animation config --------------------------------------------------------
        #This is the frame rate of dragging animation update
        self._frame_rate = 1/80
        #This is the time of last frame detection, used to detect time lapse 
        self._last_tick = None
        #Accumulated time lapse, used for detect if a frame should be updated
        self._accumulator = 0
        #How many frames has passed since pressed
        self._frame_count = 0
        #The damped pendulum that swings the pet while dragging. Built on the first drag,
        #once the grab point is known, and dropped again on release.
        self._swing = None

        #-- Pressing Config ---------------------------------------------------------
        #This category is used to detect if mouse is continuelly pressing. Somehow PyQT5 doesn't come with a innate event checker, fuck it.
        self._pressTimer = QTimer(self)
        self._pressTimer.setTimerType(Qt.PreciseTimer)
        # QTimer works in miliseconds
        self._pressTimer.setInterval(int(self._frame_rate*1000))
        # Time out event triggers tick detection
        self._pressTimer.timeout.connect(self._frame_has_passed)

        #-- configuration -----------------------------------------------------------
        #Copied out of config.json by SettingMenu.getConfig()
        self.SETTING = None
        #The "Swing intensity" setting, used for the pendulum swing of a drag
        self._amplifier = None

        #-- dialogs -----------------------------------------------------------------
        #DIALOGS and _clickDialogExist are set by _initSettingMenu, which __init__ calls before
        #this method, so they must not be given defaults here: doing so wipes the real values.
        #One timer per dialog group; a group fires _speechBubbling at a random interval
        self._standByTimers = {}

        #-- speech bubble -----------------------------------------------------------
        #True while a bubble is on screen, so a second one cannot be started
        self._speechBubbleCondition = False
        #The bubble widget and its worker pair; all three are rebuilt per bubble
        self._speechBubble = None
        self._speechBubbleWork = None
        self._speechBubbleThread = None

        #-- wandering ---------------------------------------------------------------
        #Fires after the configured interval and sends the pet on a trip
        self._wanderingTimer = None
        #The worker and its thread, both rebuilt on every trip
        self._wanderingWork = None
        self._wanderingThread = None

        #-- setting menu ------------------------------------------------------------
        #The menu itself is built by _initSettingMenu before this method runs, so it gets no
        #default here. The dialog data it owns is the shared DIALOGS dict.

        #-- tray --------------------------------------------------------------------
        self._tray_menu = None
        self._tray_icon_menu = None

        #Legacy field, never read: the live value is _facingDirection
        self.__facingDirection = None

        #Cache one QMovie per facing direction
        for state in self.normalStates:
            movie = QMovie(state)
            movie.setCacheMode(QMovie.CacheAll)
            movie.setScaledSize(QSize(int(self.ORGINALWIDTH*self._petImageSize), int(self.ORGINALHEIGHT*self._petImageSize)))
            self._petImages.append(movie)
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
        #__init__ calls this before _init, so the two fields below are born here and must not be
        #given defaults in _init afterwards, or the real values would be wiped.
        #The menu window itself
        self._settingMenu = SettingMenu()
        #Whether the dialogs contain a clickDialog group
        self._clickDialogExist = False

        self._settingMenu.finished.connect(self._SettingMenuClose)
        self._settingMenu.warning.connect(lambda x: self._speechBubbling(x))
        #Every dialog group, handed over as the shared dict rather than copied
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
        menuSize = self._settingMenu.size()
        #Reference the PET, not the window. The window is deliberately oversized so the sprite
        #can rotate without being clipped, so measuring from it would leave the menu floating
        #out in the empty border instead of sitting beside her.
        petLeft = currPos.x() + self._spriteInset
        petTop = currPos.y() + self._spriteInset
        petSide = int(self.ORGINALWIDTH*self._petImageSize)
        #prefer the right of the pet, fall back to the left if the menu would leave the screen
        if self.WINDOWWIDTH - (petLeft + petSide) >= menuSize.width():
            x = petLeft + petSide
        else:
            x = petLeft - menuSize.width()
        y = petTop + petSide//2 - menuSize.height()//2
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
        #Create a thread to run subprocess
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
            #set when the pet is shutting down, so the loop stops touching a dying window
            self._stopRequested = False

        def requestStop(self):
            self._stopRequested = True

        def run(self):
            #The range of movement distance is movementrange "mr" pixel to both side
            #Get the current position
            currentPos = self.mainWindow.pos()
            screenSize = QApplication.primaryScreen().size()
            #random a destine position with random.randint(a,b). a and b equals to either 0 or maxscreen (width/height  - half of the desktop pet size) if out of screen. (that's some long ass code!)
            #Bound the move by the SPRITE's rect, not the window's. The window is deliberately
            #oversized so the pet can rotate without being clipped, so bounding the window
            #would keep her needlessly far from the edges of the screen.
            inset = self.mainWindow._spriteInset
            side = int(self.mainWindow.ORGINALWIDTH*self.mainWindow._petImageSize)
            #The window positions that keep the whole sprite on screen
            minX, maxX = -inset, screenSize.width() - side - inset
            minY, maxY = -inset, screenSize.height() - side - inset
            xStart = min(max(currentPos.x() - self.mr, minX), maxX)
            xEnd = min(max(currentPos.x() + self.mr, minX), maxX)
            xDestiny = random.randint(min(xStart,xEnd),max(xStart,xEnd))
            
            yStart = min(max(currentPos.y() - self.mr, minY), maxY)
            yEnd = min(max(currentPos.y() + self.mr, minY), maxY)
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
                #leave immediately if the pet is quitting, the window may already be gone
                if self._stopRequested:
                    break
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
            #set when the pet is shutting down, so the loop stops touching a dying window
            self._stopRequested = False

        def requestStop(self):
            self._stopRequested = True

        def run(self):
            #Get the size of the screen
            screenWidth = QDesktopWidget().screenGeometry(0).width()
            selfWidth = self.speechBubble.width()
            selfHight = self.speechBubble.height()
            try:
                for i in range( int(self.time2Live*30) ):
                    #leave immediately if the pet is quitting, the window may already be gone
                    if self._stopRequested:
                        return
                    mainPos = self.mainWindow.pos()
                    #Where the pet actually reaches right now. The window is not always the
                    #standing one - a press blows it up to 2R and hangs the sprite off the
                    #centre at an angle BEFORE the click dialog fires - so ask for the real
                    #outline instead of assuming an upright sprite at a fixed inset.
                    centreX = mainPos.x() + self.mainWindow.width()//2
                    centreY = mainPos.y() + self.mainWindow.height()//2
                    left, top, right, bottom = self.mainWindow._spriteExtents()

                    #Sit the bubble on the top edge of the rotated image, centred on it
                    xPos = int(centreX + (left+right)/2 - selfWidth//2)
                    yPos = int(centreY + top - selfHight)

                    #prevent the speech bubble from going off screen
                    if xPos < 0: xPos = 0
                    elif xPos+selfWidth>screenWidth: xPos = screenWidth - selfWidth
                    #If the space above desktop isn't enought, move the speech bubble down
                    if yPos < 0: yPos = int(centreY + bottom)

                    self.move.emit([int(xPos), int(yPos)])
                    #FPS
                    time.sleep(1/30)
            finally:
                #always report completion, otherwise the thread is never quit and the bubble stays locked
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
            self._frame_counter_start()
            #adjust anchor of movement position
            self._drag_pos = event.globalPos() - self.pos()
            self._previous_drag_pos = event.globalPos()
            #Initiate frame rate calculation
            #Grow the window so the sprite can swing about the grab point without ever
            #being clipped, and park the grab point at the window centre so that centre
            #is the rotation pivot.
            #Nothing moves here - not the window, not the sprite. The window only starts
            #following once the drag really begins, and until then the pet stays exactly
            #where it was, so a click cannot make it jump.
            self._dragRadius = self._windowSide//2
            self._spriteOrigin = (self._spriteInset, self._spriteInset)
            #The grab point in window coordinates IS the pivot, and _drag_pos already holds it
            self._pivotOffset = self._drag_pos
            #paintEvent draws the rotating sprite, so the gif label steps aside
            self.petLabel.hide()
            self.repaint()
            #Re-assert the mouse grab. Resizing and moving the window can drop the implicit
            #grab Qt takes on press, and once that happens the release event never arrives,
            #leaving the pet glued to the cursor. An explicit grab is rebindable, so doing
            #it AFTER the geometry change is what makes it stick.
            self.grabMouse()
            self._mouseGrabbed = True
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

    def _endDrag(self):
        '''Leave the drag state: stop following, restore the standing window and label.

        Called both by mouseReleaseEvent and by the safety net in _frame_has_passed, so
        every teardown step lives in exactly one place.
        '''
        #Stop following the cursor FIRST. If any later step misbehaves, the pet must not
        #be left glued to the mouse: "should the pet follow" is _draging AND a live
        #_dragRadius, and both are cleared before anything else runs.
        self._pressTimer.stop()
        was_drag = self._draging and self._dragged
        self._draging = False
        self._dragged = False
        #Hand the mouse back before anything else can fail, otherwise the grab would
        #outlive the drag and swallow clicks meant for other windows.
        if self._mouseGrabbed:
            self._mouseGrabbed = False
            self.releaseMouse()
        #only restore the standing gif when the pet was actually dragged, otherwise a plain click
        #would interrupt the animation that is already playing
        if was_drag:
            self._changeFacingDirection(self._facingDirection)
            self.repaint()
        #Back to the standing window. This also covers a plain click, which resized
        #and hid the label on press but never got as far as a real drag.
        if self._dragRadius is not None:
            #Shrinking the window moves the sprite: during a drag it sits at _spriteOrigin,
            #but the standing layout puts it at (MARGIN//2, MARGIN//2). Re-place the window
            #so the sprite stays put on screen instead of jumping by that difference.
            keep_x = self.pos().x() + self._spriteOrigin[0] - self._spriteInset
            keep_y = self.pos().y() + self._spriteOrigin[1] - self._spriteInset
            #The sprite is upright again, so it occupies the plain _spriteInset rect.
            #The swing may have left a corner or two off the display; slide the window back
            #by the shortest distance that brings the whole image inside.
            W = int(self.ORGINALWIDTH*self._petImageSize)
            H = int(self.ORGINALHEIGHT*self._petImageSize)
            sprite_x = keep_x + self._spriteInset
            sprite_y = keep_y + self._spriteInset
            if sprite_x < 0: keep_x -= sprite_x
            elif sprite_x + W > self.WINDOWWIDTH: keep_x -= (sprite_x + W) - self.WINDOWWIDTH
            if sprite_y < 0: keep_y -= sprite_y
            elif sprite_y + H > self.WINDOWHEIGHT: keep_y -= (sprite_y + H) - self.WINDOWHEIGHT
            #Back to the standing window in ONE geometry call: shrink and move together, so
            #Windows has no gap to present a half-restored frame in. Updates stay off until
            #the window is already in its final place.
            #Back to the standing look. There is NO resize here: the window was already the
            #standing size all along, so releasing only has to put it back where it belongs.
            self.petLabel.show()
            self._dragRadius = None
            self._spriteOrigin = None
            self._dragAngleDeg = 0.0
            self._dragPixmaps.clear()
            self._swing = None
            self.move(keep_x, keep_y)
        #resume standby phase
        self._beginStandbyPhase()
        self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseReleaseEvent(self, event):
        self._endDrag()

#Minor Functions-----------------------------------------------------------------------------------------
        
# Quit Functions (Proposed by deepseek) ----------------------------------------------------------------------------------
    #Quit the desktop pet
    def quit(self):
        self.shutdown()
        self.close()
        QApplication.instance().quit()

    def _check_if_Qt_object_is_already_deleted(self, fn):
        '''call fn, if the object contained is already deleted, skip'''
        try:
            return fn()
        except RuntimeError:
            pass

    # Why the hell did deepseek added this part when I only requested her to reorganize my code structure??
    #Stop every background worker before the window goes away.
    #Without this, a speech bubble or wander loop keeps touching the already deleted window
    #("wrapped C/C++ object of type DesktopPet has been deleted"), which aborts the process on exit.
    def shutdown(self):
        #stop the standby timers first so no new worker is spawned while we are tearing down
        self._quitStandbyPhase()
        if getattr(self, "petImage", None) is not None:

            self._check_if_Qt_object_is_already_deleted(self.petImage.stop)

        #ask the workers to leave their loops, then wait for their threads
        for threadName, workName in (("_wanderingThread", "_wanderingWork"), ("_speechBubbleThread", "_speechBubbleWork")):
            thread = getattr(self, threadName, None)
            work = getattr(self, workName, None)
            if work is not None:
                work.requestStop()
            if thread is not None:
                self._check_if_Qt_object_is_already_deleted(thread.quit)
                self._check_if_Qt_object_is_already_deleted(lambda: thread.wait(2000))

        if getattr(self, "_speechBubble", None) is not None:
            self._check_if_Qt_object_is_already_deleted(self._speechBubble.close)



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

# -- Dragging functions --------------------------------------------------------------------------
    
    def _frame_counter_start(self):
        '''Initiate the timer for dragging'''
        #initial time for pet being clicked
        self._last_tick = time.perf_counter()
        #begin counting time lapses
        self._accumulator = 0
        # Start press detector
        self._pressTimer.start()
        self._frame_count = 0

    def _frame_has_passed(self) -> bool:
        '''Calculate if a frame has passed'''
        # Get current time
        now = time.perf_counter()
        # Get time elapse between two call
        elapse = now - self._last_tick
        self._last_tick = now
        # Add time lapse, set a maximum of 0.25 second incase of program lag or none response
        self._accumulator += min(elapse, 0.25)

        # Detect if a frame has changed
        if self._accumulator >= self._frame_rate:
            # Return true if a frame has indeed changed
            self._accumulator -= self._frame_rate
            self._frame_count += 1
            if self._frame_count == 10:
                self._draging = True
                self._dragged = True
            #Safety net. If the platform drops the mouse grab, the release event never
            #arrives and the pet would stay glued to the cursor forever. Poll the actual
            #button state instead of trusting the event. The explicit grab above is the
            #real fix; this is what keeps a future regression from becoming a stuck mouse.
            if self._draging and not (QApplication.mouseButtons() & Qt.LeftButton):
                self._endDrag()
            if self._draging and self._dragRadius is not None:
                # Grant pet physic effect
                self._petDraggedMove()

        return True

    def _spriteExtents(self):
        '''How far the pet reaches from the centre of its window: (left, top, right, bottom).

        Standing, that is just half the sprite. While dragging the window centre IS the
        pivot and the pet hangs off it at an angle, so the four corners are rotated by the
        draw angle and the answer is their bounding box. Callers that need the pet's real
        outline - the edge clamp and the speech bubble - both use this, so neither has to
        assume the sprite is upright.
        '''
        W = int(self.ORGINALWIDTH*self._petImageSize)
        H = int(self.ORGINALHEIGHT*self._petImageSize)
        if self._dragRadius is None:
            return -W/2, -H/2, W/2, H/2
        #Grab point in sprite-local coordinates
        gx = self._drag_pos.x() - self._spriteInset
        gy = self._drag_pos.y() - self._spriteInset
        angle = radians(self._dragAngleDeg)
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

    def _petDraggedMove(self) -> None:
        '''Moving Pet alone with the cursor'''
        #A live drag radius is what makes the pet follow: without it there is no pivot to
        #park on the cursor, and no valid buffer to move inside.
        if self._dragRadius is None:
            return
        eventPos = QCursor.pos()
        dx = abs(self._FacingDirectionUpdate(eventPos))

        #update previous drag pos
        self._previous_drag_pos = eventPos
        #call the drag movement angle for the drag physic effect
        self._changeDragAngle(dx, eventPos)

        #The grabbed point sits at the window centre, so parking the centre on the
        #cursor keeps the grabbed spot under the mouse at every rotation angle.
        #This is what replaced the old _drag_pos + "+15" anchor correction.
        R = self._dragRadius

        #Keep the sprite on screen. The window centre is the pivot, so _spriteExtents hands
        #back the bounding box of the rotated sprite around it; clamping the pivot by those
        #four reach values keeps the whole pet inside whatever angle it is hanging at.
        left, top, right, bottom = self._spriteExtents()
        pivot_x = eventPos.x()
        pivot_y = eventPos.y()
        if pivot_x < -left: pivot_x = -left
        elif pivot_x > self.WINDOWWIDTH - right: pivot_x = self.WINDOWWIDTH - right
        if pivot_y < -top: pivot_y = -top
        elif pivot_y > self.WINDOWHEIGHT - bottom: pivot_y = self.WINDOWHEIGHT - bottom

        #Park the pivot on the cursor. On the first tick after a press this is a no-op, because
        #the cursor has not moved and the pivot is still exactly where it was grabbed.
        self.move(int(pivot_x - self._pivotOffset.x()), int(pivot_y - self._pivotOffset.y()))


    #This function decides the type of movement desktoppet is experiencing.
    def _petDragMovement(self, eventPos:int) -> None:
        #a real drag happened, so the release handler has to restore the normal gif
        pass


    #Standby phase is when there isn't any user interaction with desktop pet. 
    #During standby phase, QTimers will kick for standby behaviors and speech bubbles, but they might leads to undertermined behavior if executed during user interactions. So, they have to paused.
    def _quitStandbyPhase(self):
        for Timer in self._standByTimers.values():
            Timer.stop()

    #resume standby phase
    def _beginStandbyPhase(self):
        for Timer in self._standByTimers.values():
            Timer.start()

    def _FacingDirectionUpdate(self, eventPos) -> int:
        '''Detect change is facing direction. If X is positive, moving right; negative, moving left'''
        #decide the current facing direction by comparing two coordinates
        facingDirection = self._previous_drag_pos.x() - eventPos.x()
        #adjust the facingDirection based on the sign of difference
        self._facingDirection = 1 if facingDirection < 0 else 0
        # Return the magnitude of change
        return facingDirection

    #change facing direction
    def _changeFacingDirection(self, facingDirection):
        #"self.normalStates" is an array where 0 is the gif of facing right, 1 is the gif of facing left
        self._facingDirection = facingDirection
        #reuse the cached movie for this direction instead of building a new one
        self.petImage = self._petImages[self._facingDirection]
        if self.petLabel.movie() is not self.petImage:
            #load petImage into petLabel
            self.petLabel.setMovie(self.petImage)
            #call resize to rescale gif if apply
            self._resize()
        #only (re)start a stopped animation, so a click can't rewind the gif to frame 0
        if self.petImage.state() != QMovie.Running:
            self.petImage.start()

    def _changeDragAngle(self, dx, eventPos):
        #The swing is a damped pendulum hung from the grab point and advanced by a fixed
        #timestep. It replaces the old "dTheta = dx*amplifier" formula, which derived the
        #angle from how far the cursor had moved since the previous mouse event: that made
        #the pet swing wildly on a high-polling mouse and barely at all on a 125Hz one.
        #dx stays in the signature for compatibility but the physics no longer reads it.
    #simulate the physic effect of pet rotated due to gravity, it is aorund the piovt (where user clicks)
    #Since the grab position doesn't change during the drag, we only need it to run once
        if self._rotationMatrixTranslate:
            #The pivot angle is measured from the SPRITE centre now, not the window
            #centre: the drag window is sized to the grab (_getWindowSize), so the
            #window centre is the grab point and no longer a fixed reference.
            W = int(self.ORGINALWIDTH*self._petImageSize)
            H = int(self.ORGINALHEIGHT*self._petImageSize)
            #Grab point in sprite-local coordinates
            gx = self._drag_pos.x() - self._spriteInset
            gy = self._drag_pos.y() - self._spriteInset
            #Find the difference in Y from the centre of the sprite
            ydiff = H//2 - gy
            #Find the difference in X from the centre of the sprite
            xdiff = -(W//2 - gx)
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

            #The rotation pivot is now the window centre, and _petDraggedMove keeps that
            #centre parked exactly under the cursor, so the grabbed spot stays under the
            #mouse by construction. That is why the old "+15" anchor fudge is gone: it
            #only ever existed to compensate for rotating the pixmap about the wrong point.

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

            #The pendulum's arm and its starting angle both come from where the pet was
            #grabbed, so it is built here - the one moment the grab is known.
            self._swing = DragSwing((gx, gy), (W, H), self.grabAngle)
            self._rotationMatrixTranslate = False

        #paintEvent draws the sprite rotated about the window centre, so the only thing this
        #method has to publish is the total draw angle. theta starts at -grabAngle, so the
        #render angle is 0 on the first frame: the pet keeps the pose you grabbed it in and
        #gravity then swings it down.
        self._dragAngleDeg = self.grabAngle + self._swing.step(eventPos, self._frame_rate)
        self.update()


    def _resize(self, at=None):
        #get the width&height after resize
        newWidth = int(self.ORGINALWIDTH*self._petImageSize)
        newHeight = int(self.ORGINALHEIGHT*self._petImageSize)
        #rescale petImage with it.
        self.petImage.setScaledSize(QSize(newWidth, newHeight))
        #Big enough for the sprite at ANY rotation about ANY grab point: the window centre is
        #the rotation pivot, so the window only has to reach the farthest corner, which is the
        #diagonal. Sizing for that from the start means a drag never resizes the window.
        side = 2*int(ceil(hypot(newWidth, newHeight)))
        self._windowSide = side
        self._spriteInset = (side - newWidth)//2
        if at is None:
            self.resize(side, side)
        else:
            #Position and size in one call, for the rare resize that still happens (startup
            #and a tray scale change)
            self.setGeometry(at[0], at[1], side, side)
        #The label covers the whole window and centres the movie, matching what paintEvent
        #does with the drag sprite
        self.petLabel.setAlignment(Qt.AlignCenter)
        self.petLabel.resize(side, side)
        self.petLabel.move(0, 0)

    def _dragSprite(self, direction):
        '''Scaled drag sprite for a facing direction, built once and reused.'''
        W = int(self.ORGINALWIDTH*self._petImageSize)
        H = int(self.ORGINALHEIGHT*self._petImageSize)
        key = (direction, W, H)
        if key not in self._dragPixmaps:
            self._dragPixmaps[key] = QPixmap(self.dragState[direction]).scaled(W, H)
        return self._dragPixmaps[key]

    def paintEvent(self, event):
        #While dragging the pet is drawn here instead of by petLabel, rotated about the
        #window centre that _petDraggedMove keeps parked under the cursor. Rotating in the
        #painter is what lets the sprite take any angle without ever being clipped.
        if self._dragRadius is None:
            return
        pivotX, pivotY = self._pivotOffset.x(), self._pivotOffset.y()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.translate(pivotX, pivotY)
        painter.rotate(self._dragAngleDeg)
        painter.translate(-pivotX, -pivotY)
        painter.drawPixmap(self._spriteOrigin[0], self._spriteOrigin[1],
                           self._dragSprite(self._facingDirection))
        
        

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