import os , sys, random
from PyQt5.QtGui import *
from PyQt5.QtCore import *
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



    def initPetImage(self):
        #initialize a Qlabel and set parent window to self(DesktopPet class)
        self.talkLabel = QLabel(self)
        #Set the stylesheet of talkLabel, just like CSS 
# require further adjustment
        self.talkLabel.setStyleSheet("font: 15pt 'Saitamaar'; border-width: 1px; color: blue;")

        #set the window for Desktop pet
        self.petLabel = QLabel(self)
        #QMovie can store motion pictures like gif
        self.petImage = QMovie("normalState/Sekibanki1.gif")

        #resize the loaded gif to fit self(DesktopPet)
        #self.petImage.setScaledSize(QSize(200,200))

        #Use setMovie to put petImage into petLabel
        self.petLabel.setMovie(self.petImage)

        #Resize window according to the loaded image
        self.resize(412, 372)
        self.petImage.start()
        
        self.show()


    def mousePressEvent(self, event):
        #accept if left mouse button
        if event.button() == Qt.LeftButton:
            self.draging = True
        else:
             self.draging = False
        #adjust anchor of movement position
        self.drag_pos = event.globalPos() - self.pos()
        event.accept()
        #Change the cursor type while draging
        self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseMoveEvent(self, event):
        # If left mouse button is pressed and pet is in drag state
        if Qt.LeftButton and self.draging:
            #pet following mouse 
            self.move(event.globalPos() - self.drag_pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.draging = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def quit(self):
        self.close()
        sys.exit()

    def display(self):
        if int(self.windowOpacity()) == 0:
            self.setWindowOpacity(1)
        else: 
            self.setWindowOpacity(0)


if __name__ == '__main__':
    #initialize
    app = QApplication(sys.argv)
    pet = DesktopPet()
    sys.exit(app.exec_())