import os , sys, random, time
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QWidget

class SettingMenu(QWidget):
    finished = pyqtSignal()
    
    def __init__(self) -> None:
        super().__init__()
        #Basic configs
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        #constants
        self.WINDOWWIDTH = 600
        self.WINDOWHEIGHT = 500
        #setup
        self.resize(self.WINDOWWIDTH, self.WINDOWHEIGHT)
        self.initFrame()
        self.initSetting()
        self.initSpeechSetting()

        self.switchSettingPage()
        self.show()


    def initFrame(self):
        #Set up the displaying page
        self.framePage = QWidget(self)
        self.framePage.resize(self.size())
        self.framePage.setObjectName("FramePage")
        self.styleSheetSet()
        #Set up the exitButton UI
        exitButton = QPushButton(self)
        exitButton.resize(QSize(60,60))
        exitButton.setObjectName("exitButton")

        # Adjust the position of button
        exitButton.move(self.WINDOWWIDTH-exitButton.size().width(), 0)
        # connect it to quit
        exitButton.clicked.connect(self.quit)
        #Create the stack layout for the frame
        self.stackLayout = QStackedLayout()
        self.framePage.setLayout(self.stackLayout)

    def reusableToolbar(self):
        #create the settings button that will be used for both pages
        self.settingButton = QPushButton()
        #Set a fixed size
        self.settingButton.setFixedSize(100,50)
        #Set a margine so it doesn't scramble together
        self.settingButton.setContentsMargins(10,10,5,10)
        #Apply stylesheet
        self.settingButton.setObjectName("settingButtonUnselected")

        #Connect it to switch page
        self.settingButton.clicked.connect(self.switchSettingPage)

        #create the speech settings button that will be used for both pages
        self.speechSettingButton = QPushButton()
        self.speechSettingButton.setFixedSize(100, 50)
        #Apply stylesheet
        self.speechSettingButton.setObjectName("speechSettingButtonUnselected")

        #Connect to switch page
        self.speechSettingButton.clicked.connect(self.switchSpeechSettingPage)

        #Add buttons to layout
        optionBar = QHBoxLayout()
        #Add spacing so options doesn't get squeezed to the left
        optionBar.addSpacing(10)
        optionBar.addWidget(self.settingButton)
        optionBar.addWidget(self.speechSettingButton)
        optionBar.addStretch(0)
        return optionBar
        

    
    def initSetting(self):
        #Create a new page for stack layout
        settingPage = QWidget()
        #add it too stackLayout
        self.stackLayout.addWidget(settingPage)
        #Create layout for the setting page
        settingPageLayout = QVBoxLayout()
        settingPage.setLayout(settingPageLayout)
        #add some filler space of optionBar doens't get pushed to the celling
        settingPageLayout.addSpacing(30)
        #add optionBar to setting page
        settingPageLayout.addLayout(self.reusableToolbar())
        #Change stylesheet
        self.settingButton.setObjectName("settingButtonSelected")

        settingPageLayout.addSpacing(20)
        #add movement interval setting
        movementIntervalLayout = QHBoxLayout()
        movementIntervalLayout.addSpacing(15)
        movementIntervalLayout.addWidget(QLabel("Movement Inverval: "))
        movementIntervalLayout.addStretch(0)
        self.movementIntervalStart = QLineEdit()
        self.movementIntervalEnd = QLineEdit()
        self.movementIntervalStart.setMaximumWidth(50)
        self.movementIntervalEnd.setMaximumWidth(50)
        movementIntervalLayout.addWidget(self.movementIntervalStart)
        movementIntervalLayout.addWidget(QLabel("to"))
        movementIntervalLayout.addWidget(self.movementIntervalEnd)
        movementIntervalLayout.addWidget(QLabel("Seconds"))
        movementIntervalLayout.addSpacing(15)
        settingPageLayout.addLayout(movementIntervalLayout)

        #Add a stretch to the layout for spacing
        settingPageLayout.addStretch(1)
        #add save setting button
        confirmLayout = QHBoxLayout()
        confirmLayout.addStretch(0)
        confirmButton = QPushButton()
        confirmButton.setObjectName("confimButton")
        confirmLayout.addWidget(confirmButton)
        confirmButton.setFixedSize(90,60)
        #add button to the setting page
        settingPageLayout.addLayout(confirmLayout)


        self.stackLayout.setCurrentIndex(0)

        
    def initSpeechSetting(self):
        #Create a new page for stack layout
        self.SpeechSettingPage = QWidget()
        #add it too stackLayout
        self.stackLayout.addWidget(self.SpeechSettingPage)
        #Create layout for the setting page
        SpeechSettingPageLayout = QVBoxLayout()
        self.SpeechSettingPage.setLayout(SpeechSettingPageLayout)
        #add some filler space of optionBar doens't get pushed to the celling
        SpeechSettingPageLayout.addSpacing(30)
        #add optionBar to setting page
        SpeechSettingPageLayout.addLayout(self.reusableToolbar())
        SpeechSettingPageLayout.addSpacing(20)
        #Change the stylesheet for button
        self.speechSettingButton.setObjectName("speechSettingButtonSelected")


    def switchSettingPage(self):
        self.stackLayout.setCurrentIndex(0)


    def switchSpeechSettingPage(self):
        self.stackLayout.setCurrentIndex(1)

    def quit(self):
        self.close()
        self.finished.emit()
        self.closeEvent()

    def styleSheetSet(self):
        #Setting button color schem
        buttonSelectedColor = 'black'
        buttonUnselectedColor = 'gray'
        buttonBackgroundColor = 'transparent'

        #Frame color scheme
        frameBorderColor = 'black'
        frameBackgroundColor = 'white'

        #Exit button color scheme
        exitButtonBorderColor = 'black'
        exitButtonBackgroundColor = 'white'
        exitButtonSelectedColor = 'gray'

        self.setStyleSheet(f"""
                QLabel{{
                    font-size: 20px;
                    font-weight: bold;
                }}
                           
                QWidget#FramePage{{
                    border-style: solid; 
                    border-color: {frameBorderColor}; 
                    border-radius: 50px; 
                    background-color: {frameBackgroundColor}; 
                    border-width: 12px;
                }}
                                     
                QPushButton#exitButton{{
                    border: 5px solid {exitButtonBorderColor};
                    border-radius: 30px;
                    background-color: {exitButtonBackgroundColor};
                    image: url(assets/UI/X_Unselected.png)
                }}
                QPushButton#exitButton:hover{{
                    image: url(assets/UI/X_Selected.png)
                }}
                QPushButton#exitButton:pressed{{
                    background-color: {exitButtonSelectedColor};
                    image: url(assets/UI/X_Selected.png)
                }}
                
                QPushButton#settingButtonUnselected{{
                    border: 5px solid {buttonSelectedColor};
                    border-radius: 10px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Gear_Unselected.png);
                    border-color:{buttonUnselectedColor};
                }}
                QPushButton#settingButtonUnselected:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Gear_Unselected.png)
                }}
                QPushButton#settingButtonUnselected:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Gear_Selected.png)
                }}
                
                QPushButton#settingButtonSelected{{
                    border: 5px solid {buttonSelectedColor};
                    border-radius: 10px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Gear_Selected.png);
                }}
                QPushButton#settingButtonSelected:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Gear_Selected.png);
                }}
                QPushButton#settingButtonSelected:pressed{{
                    background-color: {buttonSelectedColor};
                    image: url(assets/UI/Gear_Selected.png);
                }}
                           
                QPushButton#speechSettingButtonUnselected{{
                    border: 5px solid {buttonSelectedColor};
                    border-radius: 10px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Speech_Bubble_Unselected.png);
                }}
                QPushButton#speechSettingButtonUnselected:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Speech_Bubble_Unselected.png)
                }}
                QPushButton#speechSettingButtonUnselected:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Speech_Bubble_Selected.png)
                }}
                
                QPushButton#speechSettingButtonSelected{{
                    border: 5px solid {buttonSelectedColor};
                    border-radius: 10px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Speech_Bubble_Selected.png);
                }}

                QPushButton#speechSettingButtonSelected:pressed{{
                    background-color: {buttonSelectedColor};
                    image: url(assets/UI/Speech_Bubble_Selected.png);
                }}

                QPushButton#confimButton{{
                    border: 5px solid {buttonUnselectedColor};
                    border-radius: 30px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Checkmark_Unselected.png);
                }}
                QPushButton#confimButton:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Checkmark_Unselected.png)
                }}
                QPushButton#confimButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Checkmark_Selected.png)
                }}
        """)        

app = QApplication(sys.argv)
temp = SettingMenu()
sys.exit(app.exec())    