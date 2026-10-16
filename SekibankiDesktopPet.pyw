import os , sys, random, time
from PyQt5.QtCore import QObject
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import *
from SettingBox import SettingMenu
from TrayMode import TrayMode
from math import pi, atan,atan2, cos, sin, radians, hypot, ceil
from PhysicalModule import DragSwing
try:
    #Playback backend. See _playSound for why QSoundEffect was dropped.
    #The pet is Windows-only, but keep the import soft so a stray non-Windows run survives.
    import winsound
except ImportError:
    winsound = None

#Windows identifies taskbar buttons by AppUserModelID, not by window. Left alone, every window
#hosted by pythonw.exe lands in one group named after pythonw itself, and the taskbar BUTTON
#keeps pythonw's icon no matter what setWindowIcon() puts on the window (the window icon only
#reaches the title bar, Alt+Tab and the hover card). Naming this process explicitly makes
#Windows treat the pet as its own application, and the button then falls back to the window
#icon - the ico. It has to happen before any UI exists, which is why it sits at module level:
#Microsoft, on SetCurrentProcessExplicitAppUserModelID: "must be called during an application's
#initial startup routine before the application presents any UI". The id is part of the app's
#identity - changing it later makes Windows see a different application and drops pinned items.
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Sekibanki.DesktopPet")
except Exception:
    pass
#Inspired by: https://zhuanlan.zhihu.com/p/521580516

#Where the sound effects live. Derived from this file's own location rather than from the
#working directory: the pet also ships as an .exe and can be launched from anywhere.
def _assetRoot():
    '''Folder that holds assets/.

    Three cases, in order: running from source (the folder this file lives in); a frozen
    build that bundled the assets (PyInstaller's temp extraction dir); a frozen build
    shipped next to an assets/ folder (the folder holding the .exe). The pet's other asset
    paths are still relative to the working directory, so a frozen build has to be started
    from the project folder either way - but the sounds must not silently go missing just
    because __file__ points into PyInstaller's temp dir.
    '''
    candidates = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(bundle)
        candidates.append(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.getcwd())
    for root in candidates:
        if os.path.isdir(os.path.join(root, "assets")):
            return root
    return candidates[0]


SOUND_DIR = os.path.join(_assetRoot(), 'assets', 'Sound')
#Click feedback timing: how long the squash lasts, how far the pet squashes at its lowest
#point, and the animation frame interval. Deliberately independent of _frame_rate, which
#belongs to the drag.
#The squash is drawn in a fixed number of steps. Driving it by frame index rather than by
#the clock is deliberate: a clock-driven animation on a loaded event loop simply drops most
#of its frames - the pet snaps from nearly upright to squashed and back in two or three
#visible steps, which is exactly what happened when only 2-4 ticks fitted into 250 ms.
#Frame-driven, a busy loop makes the animation take a little longer instead of destroying it.
SQUASH_FRAMES = 16
#Nominal length of the animation, and the hard cap. The cap matters because a starved event
#loop must not be able to leave the pet stuck mid-animation: past it the animation is cut
#short and control goes back to standby.
SQUASH_DURATION = 0.25
SQUASH_MAX_DURATION = 1.0
SQUASH_DEPTH = 0.2
SQUASH_INTERVAL_MS = 16

class DesktopPet(QWidget):
    #initialization process
    def __init__(self, parent=None, **kwargs):
        super().__init__()
        #initialize setting menu and grab the config list
        self._initSettingMenu()
        #initialize the window
        self._init()
        #build and warm up the sound effects, now that SETTING is loaded
        self._initSound()
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
        #-- window mode -------------------------------------------------------------
        #How the pet is realised on screen, behind one interface. Everything that depends on
        #that choice goes through this object: window flags and size, where the pet is, and
        #how a drag moves it. The rest of this file never asks which mode it is.
        self._mode = TrayMode(self)
        #FramelessWindowHint: create a frameless window
        #WindowStaysOnTopHint: keep window on top
        #The third flag is the mode's business; see TrayMode.configureWindow.
        self._mode.configureWindow()

        #The window has no title bar, so nothing draws this text. It is what the taskbar
        #hover tip, Alt+Tab and the OBS window list read though, which is the whole point:
        #with showInTaskbar off this window is a SubWindow and appears in none of them.
        self.setWindowTitle("赤蛮奇")
        #Window icon, same file the tray icon uses. Without this the window has no icon of
        #its own, so Windows falls back to the interpreter's (the python/pythonw logo) for
        #the taskbar button and Alt+Tab. The ico only carries a 16x16 frame, so the taskbar
        #upscales it to 32x32 and above - it reads, but it is soft.
        self.setWindowIcon(QIcon(os.path.join('assets/icon.ico')))

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
        #Screen size is the window mode's answer now; see self._mode.screenRect().
        #Sprite canvas size, read from the artwork itself rather than hardcoded. Every layout
        #constant in this file is derived from these two numbers, so swapping in a
        #differently sized set of drawings no longer means hunting for a magic 549 that
        #nothing warns you has gone stale.
        self.ORGINALWIDTH, self.ORGINALHEIGHT = self._readSpriteSize()
        #Blank border kept around the pet so a rotated or enlarged sprite is not clipped
        self.MARGIN = 250
        #Scale of the standing gif and of the drag sprite
        self._petImageSize = 0.8
        #Where the grab point sits inside the window, i.e. the rotation pivot. The pivot does
        #NOT have to be the window centre: keeping it wherever it already is means pressing
        #down never has to move the window, which is what made the pet appear to jump.
        self._pivotOffset = None

        #-- click feedback ----------------------------------------------------------
        #Sound effects, filled in by _initSound
        self._sfx = {}
        #True while the click squash owns the pet; every mouse event is swallowed until then
        self._busy = False
        #Drives the squash animation. It cannot reuse the drag frame counter: that one runs
        #off _pressTimer, which _endDrag has already stopped by the time a squash starts,
        #and it would also need mouse events, of which there are none while squashing.
        self._squashTimer = QTimer(self)
        self._squashTimer.setInterval(SQUASH_INTERVAL_MS)
        self._squashTimer.timeout.connect(self._squashTick)
        self._squashStart = 0.0
        #Which step of the squash is being drawn. Frame-driven, see _squashTick.
        self._squashFrame = 0
        #The static drag sprite the squash is drawn from, or None when no squash is running
        self._squashPixmap = None

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

    #The window's side length and the sprite's blank border live in the window mode now.
    #They stay readable (and writable) on the window itself because the speech-bubble and
    #wandering code, plus the drag-angle maths, still ask the window for them; forwarding
    #keeps that code untouched.
    @property
    def _windowSide(self):
        return self._mode.windowSide

    @_windowSide.setter
    def _windowSide(self, value):
        self._mode.windowSide = value

    @property
    def _spriteInset(self):
        return self._mode.spriteInset

    @_spriteInset.setter
    def _spriteInset(self, value):
        self._mode.spriteInset = value

    #-- window-mode forwards ----------------------------------------------------
    #The nested workers (wandering, speech bubble) hold the WINDOW rather than the mode, so
    #these let them ask where the pet is without knowing how it is realised. Positions here
    #are always screen coordinates of the PET's top-left corner.
    def petRect(self):
        return self._mode.petRect()

    def petBounds(self):
        return self._mode.petBounds()

    def screenRect(self):
        return self._mode.screenRect()

    def petSize(self):
        return self._mode.petSize()

    def placePetAt(self, x, y):
        self._mode.placePetAt(x, y)

    def _readSpriteSize(self):
        '''Pixel size of the pet's artwork, read from the image files themselves.

        QImageReader takes the dimensions out of the file header without decoding a frame,
        which matters here: the standing gifs are ~2 MB and 90 frames long, and this runs
        before anything is on screen.
        '''
        for path in self.normalStates + self.dragState:
            size = QImageReader(path).size()
            if size.isValid() and not size.isEmpty():
                return size.width(), size.height()
        #Nothing readable. Keep the pet startable, on the size the shipped artwork used to be.
        print("[sprite] no readable sprite size, falling back to 549x549")
        return 549, 549

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
        pet = self.petRect()
        screen = self.screenRect()
        menuSize = self._settingMenu.size()
        #Reference the PET, not the window: measuring from the window would leave the menu
        #floating out in the empty border instead of sitting beside her.
        petRight = pet.x() + pet.width()
        petBottom = pet.y() + pet.height()
        screenRight = screen.x() + screen.width()
        screenBottom = screen.y() + screen.height()
        #prefer the right of the pet, fall back to the left if the menu would leave the screen
        if screenRight - petRight >= menuSize.width():
            x = petRight
        else:
            x = pet.x() - menuSize.width()
        y = pet.y() + pet.height()//2 - menuSize.height()//2
        if y + menuSize.height() > screenBottom:
            y = screenBottom - menuSize.height()
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
        self._teleport()

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
        #A wander must never start while the user is holding the pet: the two would fight
        #over the window position and she would jitter between the wander path and the
        #cursor. mousePressEvent interrupts a wander that is already running; this guard
        #covers the one case that leaves, a timer that had already been queued when the
        #press arrived.
        if self._pressTimer.isActive():
            return
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
        self._wanderingWork.moveSignal.connect(lambda coor: self.placePetAt(coor[0], coor[1]))

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
            #Everything below works in PET screen coordinates - the sprite's top-left corner.
            #Where the window is, or whether there even is one, is the mode's business.
            currentPos = self.mainWindow.petRect().topLeft()
            screen = self.mainWindow.screenRect()
            petSize = self.mainWindow.petSize()
            #random a destine position with random.randint(a,b). a and b equals to either 0 or maxscreen (width/height  - half of the desktop pet size) if out of screen. (that's some long ass code!)
            #Bound the move by the SPRITE's rect: that is what has to stay on screen, and it
            #is also what the user sees.
            minX, maxX = screen.left(), screen.right() - petSize.width()
            minY, maxY = screen.top(), screen.bottom() - petSize.height()
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
            x = self.mainWindow.petRect().x()
            y = self.mainWindow.petRect().y()
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
        #Never re-arm while the user is holding the pet. This also runs when an interrupted
        #wander finishes, and that happens WHILE the drag is going on - without this guard a
        #fresh wander would fire in the middle of one, which is the bug this all fixes.
        #The interval set the last time is kept, so _beginStandbyPhase can just start() it.
        if self._pressTimer.isActive():
            return
        self._wanderingTimer.start(random.randint(self.SETTING['start'], self.SETTING['end'])*1000)

    def _interruptWandering(self):
        '''Cut short a wander that is already under way, and wait for it to leave.

        Stopping the standby timers is not enough: a wander that had already started keeps
        emitting move signals at 30 fps, so it goes on dragging the window out from under the
        cursor. requestStop makes the loop leave after at most one tick; the wait matters
        because a move that lands after the drag has taken the window would displace it.
        '''
        work = getattr(self, "_wanderingWork", None)
        if work is None:
            return
        self._check_if_Qt_object_is_already_deleted(work.requestStop)
        thread = getattr(self, "_wanderingThread", None)
        if thread is not None:
            self._check_if_Qt_object_is_already_deleted(lambda: thread.wait(500))
    
    def _speechBubbling(self, text=None, id = None):
        #Don't creat new window if there is one already
        if self._speechBubbleCondition == True:
            return

        #A scheduled dialog is the pet talking to you, so it gets a voice. The click dialog
        #already answers with click.wav, and system text is not the pet speaking, so neither
        #of those gets talk.wav.
        if text is None and id is not None and id != 'clickDialog':
            self._playSound('talk')

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
        #Show the bubble straight away but fully transparent, and reveal it on the first
        #move the worker produces.
        #
        #Showing first is deliberate, and it is why this uses opacity rather than leaving the
        #window hidden: move() on a top-level window that has never been shown does NOT
        #reliably stick on Windows - the window manager overrides the position when the
        #window finally appears, which lands the bubble back at the default spot. At
        #windowOpacity 0 it is composited but invisible, so nothing is ever seen at that
        #default spot, and by the time it becomes visible the correct move has been applied.
        #The worker emits its first move on the very first loop iteration.
        self._speechBubble.setWindowOpacity(0.0)

        def placeBubble(coor, bubble=self._speechBubble):
            bubble.move(coor[0], coor[1])
            #Reveal on the first position the worker sends. That place is already the right one
            #even mid-drag, because the bubble is positioned from the sprite's own rect rather
            #than from the window - so there is nothing to wait for.
            if bubble.windowOpacity() == 0.0:
                bubble.setWindowOpacity(1.0)

        self._speechBubbleWork.move.connect(placeBubble)

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
            screen = self.mainWindow.screenRect()
            screenWidth = screen.x() + screen.width()
            selfWidth = self.speechBubble.width()
            selfHight = self.speechBubble.height()
            try:
                for i in range( int(self.time2Live*30) ):
                    #leave immediately if the pet is quitting, the window may already be gone
                    if self._stopRequested:
                        return
                    #Where the pet is. This is the SPRITE's rect, not the window's: the window
                    #is deliberately oversized, and while a drag is in progress its centre is
                    #the grab point rather than the sprite's centre - so measuring from the
                    #window puts the bubble in the wrong place. The sprite rect does not move
                    #as the pet swings, which also keeps the bubble from bobbing with it.
                    pet = self.mainWindow.petRect()

                    #Sit the bubble on the top edge of the image, centred on it
                    xPos = pet.center().x() - selfWidth//2
                    yPos = pet.top() - selfHight

                    #prevent the speech bubble from going off screen
                    if xPos < 0: xPos = 0
                    elif xPos+selfWidth>screenWidth: xPos = screenWidth - selfWidth
                    #If the space above desktop isn't enought, move the speech bubble down
                    if yPos < 0: yPos = pet.bottom()

                    self.move.emit([int(xPos), int(yPos)])
                    #FPS
                    time.sleep(1/30)
            finally:
                #always report completion, otherwise the thread is never quit and the bubble stays locked
                self.finished.emit()
    
    def _speechBubbleConditionChange(self):
        self._speechBubbleCondition = not self._speechBubbleCondition 

#-Sound-------------------------------------------------------------------------------------------------

    def _initSound(self):
        '''Collect the sound files that actually exist, keeping only their absolute paths.

        Building QSoundEffect players here was the first attempt and it was wrong: play()
        blocks the calling thread for 240-680 ms every so often. See _playSound.
        '''
        #Rebuild from scratch so calling this twice cannot leave a stale entry behind
        self._sfx = {}
        for name in ('click', 'talk'):
            path = os.path.join(SOUND_DIR, name + '.wav')
            if not os.path.isfile(path):
                #A missing effect must never stop the pet from starting
                # print("[sound] missing %s, that effect stays silent" % path)
                continue
            self._sfx[name] = os.path.abspath(path)

    def _playSound(self, name):
        '''Play one effect. Calling it again mid-playback restarts it, which is what a
        repeated click should sound like.

        QSoundEffect was the obvious choice and it does not work here. play() blocks the
        calling thread intermittently - measured at up to 680 ms, and still 243 ms on a
        repeat call. Called from a mouse handler that freezes the event loop, so the squash
        timer delivered no frame at all and its first tick saw an elapsed time already past
        the end of the animation: the pet made the noise and never moved.
        winsound's async playback returns in microseconds (measured worst case 1.9 ms).
        '''
        if winsound is None:
            return
        path = self._sfx.get(name)
        if path is None:
            return
        #SND_ASYNC returns immediately; SND_NODEFAULT keeps Windows from falling back to its
        #own beep if the file cannot be opened after all.
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC
                                 | winsound.SND_NODEFAULT)

#-Click squash------------------------------------------------------------------------------------------

    def _startSquash(self):
        '''Squash the pet once and hand control back to standby when the animation ends.'''
        #Play the sound BEFORE the clock starts. Anything that blocks inside _playSound
        #would otherwise eat the whole animation: the event loop stays frozen for longer
        #than the animation lasts, and the first tick then closes it on the spot.
        self._playSound('click')
        self._busy = True
        self._squashFrame = 0
        #Squash the STATIC drag sprite rather than the standing gif. Pressing the pet already
        #switched it to that sprite, so squashing the gif would swap the picture back to the
        #animation for the length of the squash and then swap it again on the way out, which
        #reads as the sprite glitching rather than as the pet being squashed.
        self._squashPixmap = self._dragSprite(self._facingDirection)
        self.petLabel.setPixmap(self._squashPixmap)
        self._squashStart = time.perf_counter()
        self._squashTimer.start()
        # print("Start")

    def _squashTick(self):
        '''Advance the squash by exactly one step.'''
        self._squashFrame += 1
        elapsed = time.perf_counter() - self._squashStart
        #The step count ends the animation, not the clock. The clock is only a safety cap so
        #a starved event loop cannot leave the pet squashed and unresponsive.
        if self._squashFrame >= SQUASH_FRAMES or elapsed >= SQUASH_MAX_DURATION:
            self._endSquash()
            return
        #One smooth push down and back up: 1.0 -> 0.8 -> 1.0, with no jump at either end
        scale = 1.0 - SQUASH_DEPTH * sin(pi * self._squashFrame / SQUASH_FRAMES)
        self._applySquash(scale)
        # print("squashing")

    def _endSquash(self):
        '''Stop the animation, hand the label back to the standing gif, resume standby.'''
        self._squashTimer.stop()
        self._applySquash(1.0)
        #Hand the label back to the standing animation. setMovie does not restart a running
        #QMovie, and the movies are cached, so the gif resumes on the frame it was left at.
        self._squashPixmap = None
        if self.petImage is not None:
            self.petLabel.setMovie(self.petImage)
            if self.petImage.state() != QMovie.Running:
                self.petImage.start()
        self._busy = False
        self._beginStandbyPhase()
        # print("end")

    def _applySquash(self, scale):
        '''Scale the pet vertically about its BOTTOM edge.

        petLabel centres its content, so shrinking it alone would lift the feet off the
        ground and squash the pet towards its middle. Moving the label down by half of the
        height that was lost pins the bottom edge in place, so the pet squashes downwards.

        During a click the content is the static drag sprite; the standing gif is only used
        if a squash somehow starts without one.
        '''
        W = int(self.ORGINALWIDTH*self._petImageSize)
        H = int(self.ORGINALHEIGHT*self._petImageSize)
        height = max(1, int(round(H*scale)))
        if self._squashPixmap is not None:
            self.petLabel.setPixmap(self._squashPixmap.scaled(
                W, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        elif self.petImage is not None:
            self.petImage.setScaledSize(QSize(W, height))
        self.petLabel.move(0, (H - height)//2)
        self.update()

#-Mouse Interaction--------------------------------------------------------------------------------------

    def mousePressEvent(self, event):
        #The squash animation owns the pet for its whole length. Swallow whatever arrives
        #meanwhile rather than queueing it, so a click cannot interrupt itself.
        if self._busy:
            event.accept()
            return
        #Quite standby phase, lest undetermined behavior
        self._quitStandbyPhase()
        #...and cut short a wander that is ALREADY in flight. Killing the timer is not
        #enough: the worker thread would go on moving the window at 30 fps while the drag
        #moves it too, and the pet would jitter between the two.
        self._interruptWandering()
        #Flag for pet transformation
        self._rotationMatrixTranslate = True
        

        #Enter drag event if mouse pressed is left button
        if event.button() == Qt.LeftButton and self._draggable:
            self._frame_counter_start()
            #adjust anchor of movement position
            self._previous_drag_pos = event.globalPos()
            #Initiate frame rate calculation
            #Grow the window so the sprite can swing about the grab point without ever
            #being clipped, and park the grab point at the window centre so that centre
            #is the rotation pivot.
            #Nothing moves here - not the window, not the sprite. The window only starts
            #following once the drag really begins, and until then the pet stays exactly
            #where it was, so a click cannot make it jump.
            #The window side, the sprite's place inside it and the pivot are all the window
            #mode's business. It records the grab point as the pivot and moves nothing, which
            #is what keeps a click from making the pet jump.
            self._mode.prepareDrag(event.globalPos())
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

        event.accept()
        #Change the cursor type while draging
        self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseMoveEvent(self, event):
        #Nothing may move the pet while the click animation is playing
        if self._busy:
            event.accept()
            return
        # If left mouse button is pressed and pet is in drag state
        if Qt.LeftButton and self._draging:
            #call on move function defined below
            self._petDragMovement(event.globalPos())
        event.accept()

    def _endDrag(self, clickButton=None):
        '''Leave the drag state: stop following, restore the standing window and label.

        Called both by mouseReleaseEvent and by the safety net in _frame_has_passed, so
        every teardown step lives in exactly one place. clickButton is the button that was
        released, or None when the safety net noticed the button had gone up by itself; a
        plain click only counts as one when we know it was the left button.
        '''
        #Stop following the cursor FIRST. If any later step misbehaves, the pet must not
        #be left glued to the mouse: "should the pet follow" is _draging AND a live
        #_dragRadius, and both are cleared before anything else runs.
        self._pressTimer.stop()
        was_drag = self._draging and self._dragged
        #A plain click is a left press that took the draggable path but never grew into a
        #drag. _dragRadius is only ever set by that path and is still set at this point, so
        #it is a reliable witness. The safety net passes no button and can never qualify,
        #which is right: it only fires once a drag is already under way.
        plainClick = (not was_drag) and clickButton == Qt.LeftButton
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
        if self._mode.isDragging():
            #Geometry teardown belongs to the mode. It has to run BEFORE the drag state is
            #cleared, because where the pet ends up depends on _spriteOrigin.
            self._mode.endDrag()
            #Back to the standing look. There is NO resize here: the window was already the
            #standing size all along, so releasing only has to put it back where it belongs.
            self.petLabel.show()
            self._dragRadius = None
            self._spriteOrigin = None
            self._dragAngleDeg = 0.0
            self._dragPixmaps.clear()
            self._swing = None
        if plainClick:
            #A plain click is the only thing that talks. It is also the only thing that
            #squashes, so both share one definition of "a click": a right press opens the
            #menu instead, a press that grew into a drag is not one, and neither is the
            #safety net (it passes no button).
            #Firing on RELEASE rather than on press is what makes that possible - whether the
            #press grew into a drag is only known once the button comes up. It also means the
            #pet is already standing again, so the bubble is placed against the upright sprite.
            self._triggerClickDialog()
            #A plain click answers with the squash animation. The animation holds the pet for
            #its whole length and only resumes standby when it finishes, so wandering cannot
            #start halfway through it.
            self._startSquash()
        else:
            #resume standby phase
            self._beginStandbyPhase()
        self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseReleaseEvent(self, event):
        if self._busy:
            event.accept()
            return
        self._endDrag(event.button())

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
        #and the click animation, so its timer cannot fire into a half-dead window
        self._squashTimer.stop()
        if getattr(self, "petImage", None) is not None:

            self._check_if_Qt_object_is_already_deleted(self.petImage.stop)

        #silence the sound effects
        if winsound is not None:
            self._check_if_Qt_object_is_already_deleted(
                lambda: winsound.PlaySound(None, winsound.SND_PURGE))

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

    def _randomPos(self) -> int:
        '''A random spot on the screen where the pet fits. Delegates to the window mode.'''
        point = self._mode.randomPetPos()
        return (point.x(), point.y())

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
            if self._draging and self._mode.isDragging():
                # Grant pet physic effect
                self._petDraggedMove()

        return True

    def _spriteExtents(self):
        '''How far the pet reaches from the centre of its window: (left, top, right, bottom).

        Standing, that is just half the sprite; dragging, it is the bounding box of the
        rotated sprite. Callers that need the pet's real outline - the edge clamp and the
        speech bubble - both use this, so neither has to assume the sprite is upright.
        Delegates to the window mode.
        '''
        return self._mode.reachFromPivot()

    def _petDraggedMove(self) -> None:
        '''Moving Pet alone with the cursor'''
        #A live drag state is what makes the pet follow: without it there is no pivot to
        #park on the cursor, and no valid buffer to move inside.
        if not self._mode.isDragging():
            return
        eventPos = QCursor.pos()
        dx = abs(self._FacingDirectionUpdate(eventPos))

        #update previous drag pos
        self._previous_drag_pos = eventPos
        #call the drag movement angle for the drag physic effect
        self._changeDragAngle(dx, eventPos)

        #Park the pivot on the cursor, and keep the whole pet on screen while doing it.
        #On the first tick after a press this is a no-op, because the cursor has not moved
        #and the pivot is still exactly where it was grabbed.
        self._mode.followCursor(eventPos)


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
            #amp = config.json 的 amplifier（摇晃强度），只乘驱动项：摆动周期、回正手感、
            #按下瞬间的姿态都不受它影响，改的只是被甩起来的幅度。
            self._swing = DragSwing((gx, gy), (W, H), self.grabAngle,
                                    amp=self._amplifier)
            self._rotationMatrixTranslate = False

        #paintEvent draws the sprite rotated about the window centre, so the only thing this
        #method has to publish is the total draw angle. theta starts at -grabAngle, so the
        #render angle is 0 on the first frame: the pet keeps the pose you grabbed it in and
        #gravity then swings it down.
        self._dragAngleDeg = self.grabAngle + self._swing.step(eventPos, self._frame_rate)
        self.update()


    def _resize(self, at=None):
        '''Rebuild the window for the current sprite scale. Delegates to the window mode.'''
        self._mode.applyScale(at)

    def _dragSprite(self, direction):
        '''Scaled drag sprite for a facing direction, built once and reused.'''
        W = int(self.ORGINALWIDTH*self._petImageSize)
        H = int(self.ORGINALHEIGHT*self._petImageSize)
        key = (direction, W, H)
        if key not in self._dragPixmaps:
            self._dragPixmaps[key] = QPixmap(self.dragState[direction]).scaled(W, H)
        return self._dragPixmaps[key]

    def paintEvent(self, event):
        #While dragging the pet is drawn here instead of by petLabel, rotated about the pivot
        #that followCursor keeps parked under the cursor. Rotating in the painter is what lets
        #the sprite take any angle without ever being clipped.
        if not self._mode.isDragging():
            return
        #Where to draw, and what to rotate about, are the mode's answers: in tray mode the
        #sprite sits at a fixed inset in a window that follows the pet, in full-screen mode
        #its place inside the window IS the pet's position.
        pivot = self._mode.pivotInWindow()
        origin = self._mode.spriteOriginInWindow()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.translate(pivot.x(), pivot.y())
        painter.rotate(self._dragAngleDeg)
        painter.translate(-pivot.x(), -pivot.y())
        painter.drawPixmap(origin.x(), origin.y(), self._dragSprite(self._facingDirection))
        
        

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
        point = self._mode.randomPetPos()
        self._mode.placePetAt(point.x(), point.y())
        
        

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