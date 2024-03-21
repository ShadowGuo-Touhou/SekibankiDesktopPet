import os , sys, random, time
from PyQt5.QtCore import QObject
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import *

#Inspired by: https://zhuanlan.zhihu.com/p/521580516

class DesktopPet(QWidget):
    #initialization process
    def __init__(self, parent=None, **kwargs):
        super().__init__()
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

#Initialization------------------------------------------------------------------------------------------
        
    def _init(self):
        #FramelessWindowHint: create a frameless window
        #WindowStaysOnTopHint: keep window on top
        #SubWIndow: keep the window a subwindow regardless of the existance of parent window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)

        #Don't fill window with background color
        self.setAutoFillBackground(False)
        #Set window transparent
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        #refresh window
        self.update()

        #the facing state of pet: 0 is facing right, 1 is facing left
        self.__facingDirection = None
        #The array containing the states for desktopPet
        self.normalStates = ["normalState/Sekibanki1 right.gif", "normalState/Sekibanki1 left.gif"]
        
        #Constants
        self.WINDOWWIDTH = QApplication.primaryScreen().size().width()
        self.WINDOWHEIGHT = QApplication.primaryScreen().size().height()
        


    def _initTrayIcon(self):
        #import prepared trayicon image
        iconImage = os.path.join('icon.ico')
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
        self._tray_icon_menu.addAction(quit_action)
        self._tray_icon_menu.addAction(display_action)

        self._tray_menu.setContextMenu(self._tray_icon_menu)
        self._tray_menu.show()

    
    def _initDialog(self):
        #load dialog file in a list
        self._standByDialogs = []
        #Open local file
        try:
            with open("dialogs/standByDialogs.txt") as f:
                self._standByDialogs = f.read().split("\n")
                length = len(self._standByDialogs)
                i = 0
                while i < length:
                    if self._standByDialogs[i][0] == '#':
                        self._standByDialogs.remove(self._standByDialogs[i])
                        i -= 1
                        length -= 1
                    i += 1
        except Exception as e:
            print(e)
            self._standByDialogs.append("dialogs/standByDialogs.txt doesn't exist or corrupted.")
        #Click dialog
        self._clickDialogs = []
        try:
            with open("dialogs/clickDialogs.txt") as f:
                self._clickDialogs = f.read().split("\n")
                length = len(self._clickDialogs)
                i = 0
                while i < length:
                    if self._clickDialogs[i][0] == '#':
                        self._clickDialogs.remove(self._clickDialogs[i])
                        i -= 1
                        length -= 1
                    i += 1
        except Exception as e:
            print(e)
            self._clickDialogs.append("dialogs/clickDialogs.txt doesn't exist or corrupted.")



#Pet ImageDisplay----------------------------------------------------------------------------------------

    def _initPetImage(self):
        #create a label that stores the image of pet
        self.petLabel = QLabel(self)

        #randomly choose a starting facing direction for pet
        self._changeFacingDirection(random.randint(0,1))

        # #Resize window according to the loaded imagese
        self.resize(421, 372)
        
        #go to a random position on the desktop
        randomPos = self._randomPos()
        self.move(randomPos[0], randomPos[1])
        
        #Display self (this is different from opacity)
        self.show()


#Pet Standby Actions-------------------------------------------------------------------------------------

    def _initStandBy(self):
        #Create a timer for wandering function, where the pet moves around the desktop
        self._wanderingTimer = QTimer(self)
        #once the timer time out, trigger _wandering function
        self._wanderingTimer.timeout.connect(self._wandering)
        #set the interval for 
        self._wanderingTimer.setInterval(random.randint(20, 300)*1000)
        self._wanderingTimer.start()
        
        #Create a timer for standby phase, the logic is the same with wandering timer
        self._speechBubbleTimer = QTimer(self)
        self._speechBubbleTimer.timeout.connect(self._speechBubbling)
        self._speechBubbleTimer.setInterval(random.randint(20, 300)*1000) # 20 ~ 120 seconds
        self._speechBubbleTimer.start()

    #the function for wandering, becauses it involves a loop that can't be put in the main loop, we need another thread for it
    def _wandering(self):
        #create a thread to run subprocess
        self._wanderingThread = QThread(parent=self)
        #create the wandering class and pass in self(DesktopPet)
        self._wanderingWork = self._WanderingWork(self)
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

        #Start the thread 
        self._wanderingThread.start()

        
    #create a class that inherites QObject so QThread recognizes and runs it
    class _WanderingWork(QObject):
        #Create a signal to indicate the end of the thread process
        finished = pyqtSignal()
        moveSignal = pyqtSignal(list)
        changeFacingDirectionSignal = pyqtSignal(int)

        def __init__(self, mw):
            #initialize super class
            super().__init__()
            #pass in the DesktopPet class so we can call on its move function
            self.mainWindow = mw

        def run(self):
            #The range of movement distance is movementrange "MR" pixel to both side
            #Get the current position
            currentPos = self.mainWindow.pos()
            screenSize = QApplication.primaryScreen().size()
            mr = 300
            #random a destine position with random.randint(a,b). a and b equals to either 0 or maxscreen (width/height  - half of the desktop pet size) if out of screen. (that's some long ass code!)
            xDestiny = random.randint(currentPos.x() - mr if currentPos.x() > mr else 0, currentPos.x() + mr if screenSize.width() - mr < currentPos.x() else screenSize.width()-self.mainWindow.size().width())
            yDestiny = random.randint(currentPos.y() - mr if currentPos.y() > mr else 0, currentPos.y() + mr if screenSize.height() - mr < currentPos.y() else screenSize.height()-self.mainWindow.size().height())
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

    
    def _speechBubbling(self, text = None, T2T = 5):
        #Create an instance of speech bubble and set the text it displays
        self._speechBubble = self._SpeechBubbleClass()
        if text != None:
            self._speechBubble.setText(text)
        else:
            self._speechBubble.setText(random.choice(self._standByDialogs))
        #Create a thread for speechbubble
        self._speechBubbleThread = QThread(parent=self)
        self._speechBubbleWork = self._SpeechBubbleWork(self, self._speechBubble, T2T)
        #move to thread
        self._speechBubbleWork.moveToThread(self._speechBubbleThread)
        #connect the start of thread to speechBubbleWork's run function
        self._speechBubbleThread.started.connect(self._speechBubbleWork.run)
        self._speechBubbleThread.finished.connect(self._speechBubbleThread.deleteLater)
        self._speechBubbleWork.finished.connect(self._speechBubbleThread.quit)
        self._speechBubbleWork.finished.connect(self._speechBubbleWork.deleteLater)
        self._speechBubbleWork.finished.connect(self._speechBubble.deleteLater)
        self._speechBubbleWork.move.connect(lambda coor: self._speechBubble.move(coor[0], coor[1]))

        self._speechBubbleThread.start()
        self._speechBubble.show()


    #Speech bubble functions
    #Speech bubble is displayed above Desktop pet for a certain period of time when triggered.
    #Define a class for SpeechBubble for abstraction/code encapsulation
    class _SpeechBubbleClass(QMainWindow):
        def __init__(self):
            super().__init__()
            #basic settings
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            #Text display
            self._textBox = QLabel(self)
            self._textBox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._textBox.setMargin(20)
            self._textBox.setStyleSheet("border-style: groove; border-width: 5px; border-radius: 20px;background-color: rgba(255, 255, 255, 150); font-size: 30px; color: rgb(0,0,0)")
            font = QFont('Saitamaar.ttf',20)
            self._textBox.setFont(font)
            #Put Qlabel into the speech bubble
            self.setCentralWidget(self._textBox)

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
                yPos = mainPos.y() - selfHight

                #prevent the speech bubble from going off screen
                if xPos < 0: xPos = 0
                elif xPos+selfWidth>screenWidth: xPos = screenWidth - selfWidth
                #If the space above desktop isn't enought, move the speech bubble down
                if yPos < 0: yPos = mainPos.y() + mainHeight + selfHight//2

                self.move.emit([xPos, yPos])
                #FPS
                time.sleep(1/30)
            self.finished.emit()
    
#-Mouse Interaction--------------------------------------------------------------------------------------

    def mousePressEvent(self, event):
        #Quite standby phase, lest undetermined behavior
        self._quitStandbyPhase()

        #Enter drag event if mouse pressed is left button
        if event.button() == Qt.LeftButton:
            self._draging = True
            #adjust anchor of movement position
            self._drag_pos = event.globalPos() - self.pos()
            self._previous_drag_pos = event.globalPos()
        else:
            self._draging = False
        
        #Trigger click dialog for 20% chance
        if random.randint(1, 100)<=20: self._speechBubbling(random.choice(self._clickDialogs), 0.5)


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
        if int(self.windowOpacity()) == 0:
            self.setWindowOpacity(1)
        else: 
            self.setWindowOpacity(0)

    #Choose a random point on the screen where desktop pet won't go off screen
    def _randomPos(self) -> int:
        screenSize = QDesktopWidget().screenGeometry(0)
        petSize = self.size()
        return random.randint(0, screenSize.width()-petSize.width()//2), random.randint(0, screenSize.height()-petSize.height()//2)
    
    #This function decides the type of movement desktoppet is experiencing.
    def _petDragMovement(self, eventPos:int, ) -> None:
        #decide the current facing direction by mius
        facingDirection = self._previous_drag_pos.x() - eventPos.x()
        if facingDirection <0: facingDirection = 1
        elif facingDirection >0: facingDirection = 0
        
        if self._facingDirection == facingDirection:
            pass
        else:
            self._changeFacingDirection(1 if facingDirection == 1 else 0)
        #update previous drag pos
        self._previous_drag_pos = eventPos
        destination = eventPos-self._drag_pos
        xPos = destination.x()
        yPos = destination.y()
        if xPos < 0: xPos = 0
        elif xPos > self.WINDOWWIDTH - self.width(): xPos = self.WINDOWWIDTH - self.width()

        if yPos < 0: yPos = 0
        elif yPos > self.WINDOWHEIGHT - self.height(): yPos = self.WINDOWHEIGHT - self.height()

        self.move(xPos, yPos)

    #Standby phase is when there isn't any user interaction with desktop pet. 
    #During standby phase, QTimers will kick for standby behaviors and speech bubbles, but they might leads to undertermined behavior if executed during user interactions. So, they have to paused.
    def _quitStandbyPhase(self):
        self._wanderingTimer.stop()
        self._speechBubbleTimer.stop()

    #resume standby phase
    def _beginStandbyPhase(self):
        self._wanderingTimer.start()
        self._speechBubbleTimer.start()

    #change facing direction
    def _changeFacingDirection(self, facingDirection):
        #"self.normalStates" is an array where 0 is the gif of facing right, 1 is the gif of facing left
        self._facingDirection = facingDirection
        #load the gif into petImage
        self.petImage = QMovie(self.normalStates[self._facingDirection])
        #load petImage into petLabel
        self.petLabel.setMovie(self.petImage)
        #begin to play the gif
        self.petImage.start()
        
        

if __name__ == '__main__':
    #initialize
    app = QApplication(sys.argv)
    pet = DesktopPet()
    sys.exit(app.exec_())
