import os , sys, random
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import *

#Inspired by: https://zhuanlan.zhihu.com/p/521580516

class DesktopPet(QWidget):
    #initialization process
    def __init__(self, parent=None, **kwargs):
        super(DesktopPet, self).__init__(parent)
        #initialize the window
        self.init()
        #initialize and show pet image
        self.initPetImage()
        #initialize the tray icon for pet
        self.initTrayIcon()

#Initialization------------------------------------------------------------------------------------------
        
    def init(self):
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
        self.facingDirection = None
        #The array containing the states for desktopPet
        self.normalStates = ["normalState/Sekibanki1 right.gif", "normalState/Sekibanki1 left.gif"]

    def initTrayIcon(self):
        #import prepared trayicon image
        iconImage = os.path.join('icon.ico')
        #Create the tray icon
        self.tray_menu = QSystemTrayIcon(self)
        #set the icon image
        self.tray_menu.setIcon(QIcon(iconImage))

        #Create the tray icon menu for tray icon
        self.tray_icon_menu = QMenu(self)
        #create a quit action for the pet
        quit_action = QAction("Exit", self, triggered=self.quit)
        #create a display or hide the pet
        display_action = QAction("Display/Hide", self, triggered=self.display)
        #Add two events to the menu
        self.tray_icon_menu.addAction(quit_action)
        self.tray_icon_menu.addAction(display_action)

        self.tray_menu.setContextMenu(self.tray_icon_menu)
        self.tray_menu.show()
    


#Pet ImageDisplay----------------------------------------------------------------------------------------

    def initPetImage(self):
        #initialize a Qlabel and set parent window to self(DesktopPet class)
        self.talkLabel = QLabel(self)
        #Set the stylesheet of talkLabel, just like CSS

# require further adjustment
        self.talkLabel.setStyleSheet("font: 15pt 'Saitamaar'; border-width: 1px; color: blue;")

        #set the window for Desktop pet
        self.petLabel = QLabel(self)
        #QMovie can store motion pictures like gif
        #Load into normal state, randomly choose a facing
        if random.randint(0,1) == 0:
            self.facingDirection = 1
        else:
            self.facingDirection = 1

        self.petImage = QMovie(self.normalStates[self.facingDirection])


        #resize the loaded gif to fit self(DesktopPet)
        #self.petImage.setScaledSize(QSize(200,200))

        #Use setMovie to put petImage into petLabel
        self.petLabel.setMovie(self.petImage)

        #Resize window according to the loaded image
        self.resize(412, 372)
        self.petImage.start()
        
        #go to a random position on the desktop
        randomPos = self.randomPos()
        self.move(randomPos[0], randomPos[1])
        
        #Display self (this is different from opacity)
        self.show()

#-Mouse Interaction--------------------------------------------------------------------------------------

    def mousePressEvent(self, event):
        #Enter drag event if mouse pressed is left button
        if event.button() == Qt.LeftButton:
            self.draging = True
            #adjust anchor of movement position
            self.drag_pos = event.globalPos() - self.pos()
            self.previous_drag_pos = event.globalPos()
        else:
            self.draging = False


        event.accept()
        #Change the cursor type while draging
        self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseMoveEvent(self, event):
        # If left mouse button is pressed and pet is in drag state
        if Qt.LeftButton and self.draging:
            #call on move function defined below
            self.petMoveEvent(event.globalPos())
        event.accept()

    def mouseReleaseEvent(self, event):
        self.draging = False
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
    def randomPos(self) -> int:
        screenSize = QDesktopWidget().screenGeometry(0)
        petSize = self.size()

        return random.randint(petSize.width(), screenSize.width()-petSize.width()), random.randint(petSize.height(), screenSize.height()-petSize.height())
    
    #This function decides the type of movement desktoppet is experiencing.
    def petMoveEvent(self, eventPos:int, ) -> None:
        #decide the current facing direction by mius
        facingDirection = self.previous_drag_pos.x() - eventPos.x()
        if facingDirection <0: facingDirection = 1
        elif facingDirection >0: facingDirection = 0
        
        if self.facingDirection == facingDirection:
            pass
        else:
            # print(self.facingDirection, facingDirection)

            if self.facingDirection == 0: self.facingDirection = 1
            else: self.facingDirection = 0

            self.petImage = QMovie(self.normalStates[self.facingDirection])
            self.petLabel.setMovie(self.petImage)

            self.petImage.start()
        #update previous drag pos
        self.previous_drag_pos = eventPos
        self.move(eventPos-self.drag_pos)
        
    
        

if __name__ == '__main__':
    #initialize
    app = QApplication(sys.argv)
    pet = DesktopPet()
    sys.exit(app.exec_())