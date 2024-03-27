import os , sys, random, time, json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QWidget

class SettingMenu(QWidget):
    finished = pyqtSignal()
    #desktop pet will announce when setting changed
    begin = pyqtSignal()
    #Send warning when user enter illegal settings
    warning = pyqtSignal(str)
    
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
        self.initRead()

        self.initFrame()
        self.initSetting()
        self.initSpeechSetting()
        self.switchSettingPage()

        self.styleSheetSet()

        self.setStyleSheet(self.StyleSheet)

#Read settings and dialogs-------------------------------------------------------------------------------
    def initRead(self):
        #Load config file
        try:
            with open('assets/Settings/config.json') as s:
                self.SETTING = json.load(s)
        except Exception as e:
            print(e)
            self.warning.emit(str(e))
            self.SETTING = {'start':20, 'end':300, 'language': 0}
        #Load language file
        try:
            with open('assets/Settings/EN.json' if self.SETTING['language'] == 0 else 'assets/Settings/CN.json') as s:
                self.LANGUAGE = json.load(s)
        except Exception as e:
            print(e)
            self.warning.emit(str(e))
            self.LANGUAGE = {"moveInterval": "Movement Interval", "to": "to", "seconds": "seconds.", "language": "language", "illegalInputWarning": "Not gonna work, check your inputs, dummy.", "successfulSave": "Got it. I'll make the change after restart."}
        

#Ititalize the window being displayed--------------------------------------------------------------------
    def initFrame(self):
        #Set up the displaying page
        self.framePage = QWidget(self)
        self.framePage.resize(self.size())
        self.framePage.setObjectName("FramePage")
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

#Display the setting page--------------------------------------------------------------------------------
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
        movementIntervalLayout.addWidget(QLabel(self.LANGUAGE['moveInterval']))
        movementIntervalLayout.addStretch(0)

        self.movementIntervalStart = QLineEdit()
        #restrict the input type of user
        self.movementIntervalStart.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9][0-9][0-9]")))
        #setting default value
        self.movementIntervalStart.setText(str(self.SETTING['start']))

        self.movementIntervalEnd = QLineEdit()
        #restrict the input type of user
        self.movementIntervalEnd.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9][0-9][0-9]")))
        #setting default value
        self.movementIntervalEnd.setText(str(self.SETTING['end']))

        self.movementIntervalStart.setMaximumWidth(50)
        self.movementIntervalEnd.setMaximumWidth(50)
        movementIntervalLayout.addWidget(self.movementIntervalStart)
        movementIntervalLayout.addWidget(QLabel(self.LANGUAGE['to']))
        movementIntervalLayout.addWidget(self.movementIntervalEnd)
        movementIntervalLayout.addWidget(QLabel(self.LANGUAGE['seconds']))
        movementIntervalLayout.addSpacing(15)
        settingPageLayout.addLayout(movementIntervalLayout)

        #add language selection
        languageLayout = QHBoxLayout()
        languageLayout.addSpacing(15)
        languageLayout.addWidget(QLabel(self.LANGUAGE['language']))
        languageLayout.addStretch(0)
        self.languageChoice = QComboBox()
        self.languageChoice.addItem("English")
        self.languageChoice.addItem("中文")
        self.languageChoice.setFixedSize(100,40)
        self.languageChoice.setCurrentIndex(self.SETTING['language'])
        languageLayout.addWidget(self.languageChoice)
        languageLayout.addSpacing(15)

        settingPageLayout.addLayout(languageLayout)

        #Add a stretch to the layout for spacing
        settingPageLayout.addStretch(1)
        #add save setting button
        confirmLayout = QHBoxLayout()
        confirmLayout.addStretch(0)
        confirmButton = QPushButton()
        confirmButton.setObjectName("confimButton")
        confirmLayout.addWidget(confirmButton)
        confirmButton.setFixedSize(90,60)
        confirmButton.clicked.connect(self.SaveSetting)
        #add button to the setting page
        settingPageLayout.addLayout(confirmLayout)

        self.stackLayout.setCurrentIndex(0)


    def SaveSetting(self):
        #emit signal
        start = int(self.movementIntervalStart.text())
        end = int(self.movementIntervalEnd.text())
        if start>= end:
            self.warning.emit(self.LANGUAGE['illegalInputWarning'])
            return
        language = self.languageChoice.currentIndex()
        with open('assets/Settings/config.json', 'w+') as s:
            json.dump({'start': start, 'end': end, 'language': language}, s)

        self.warning.emit(self.LANGUAGE['successfulSave'])
        self.quit()

#Initialize speech bubble setting page-------------------------------------------------------------------
             
    def initSpeechSetting(self):
        #Create a new page for stack layout
        self.SpeechSettingPage = QWidget()
        #add it too stackLayout
        self.stackLayout.addWidget(self.SpeechSettingPage)
        #Create layout for the setting page
        speechSettingPageLayout = QVBoxLayout()
        self.SpeechSettingPage.setLayout(speechSettingPageLayout)
        #add some filler space of optionBar doens't get pushed to the celling
        speechSettingPageLayout.addSpacing(30)
        #add optionBar to setting page
        speechSettingPageLayout.addLayout(self.reusableToolbar())
        speechSettingPageLayout.addSpacing(20)
        #Change the stylesheet for button
        self.speechSettingButton.setObjectName("speechSettingButtonSelected")
        #Because the layout for speechsetting is more complicated, we use a grid layout
        speechSettingPageMinorLayout = QGridLayout()
        speechSettingPageLayout.addLayout(speechSettingPageMinorLayout)
        #Create a scroll area
        speechBubbleScrollArea = QScrollArea()
        speechBubbleScrollArea.resize(500,400)
        speechSettingPageMinorLayout.addWidget(speechBubbleScrollArea, 0, 0, 4, 4)
        speechBubbleScrollArea.setObjectName("speechBubbleScrollArea")
        #Hide scrollbar
        speechBubbleScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        speechBubbleScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        #Add a container
        speechBubbleContainer = QWidget()
        speechBubbleContainer.setStyleSheet("background-color: transparent")
        speechBubbleContainerLayout = QVBoxLayout()
        speechBubbleContainer.setLayout(speechBubbleContainerLayout)
        speechBubbleScrollArea.setWidget(speechBubbleContainer)

        #Create a layout to hold options.
        speechBubbleControllerLayout = QVBoxLayout()

        speechSettingPageMinorLayout.addLayout(speechBubbleControllerLayout, 0,4, 4, 1)
        #Create option buttons
        #Add more speech slot
        addButton = QPushButton()
        addButton.setObjectName('addButton')
        addButton.setFixedSize(60,60)
        speechBubbleControllerLayout.addWidget(addButton)
        deleteButton = QPushButton()
        deleteButton.setObjectName("deleteButton")
        deleteButton.setFixedSize(60,60)
        speechBubbleControllerLayout.addWidget(deleteButton)
    

#The generate a toolbar for pages------------------------------------------------------------------------
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
        

#Minor functions-----------------------------------------------------------------------------------------
    #Swtich to setting page
    def switchSettingPage(self):
        self.stackLayout.setCurrentIndex(0)

    #Switch to speech bubble page
    def switchSpeechSettingPage(self):
        self.stackLayout.setCurrentIndex(1)

    #Written as quit, execute as hide
    def quit(self):
        self.hide()
        self.finished.emit()
    
    #Show
    def show(self):
        super().show()
        self.begin.emit()

    #return the config list
    def getConfig(self):
        return self.SETTING

#Style sheets--------------------------------------------------------------------------------------------
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

        self.StyleSheet = f"""
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
                    image: url(assets/UI/Checkmark_Unselected.png);
                }}
                QPushButton#confimButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Checkmark_Selected.png);
                }}

                QScrollArea#speechBubbleScrollArea{{
                    background-color: {buttonBackgroundColor};
                    border: 5px solid black;
                    border-radius: 20px;
                }}

                QPushButton#addButton{{
                    border:5px solid {buttonUnselectedColor};
                    border-radius: 30px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/add_Unselected.png);
                }}
                QPushButton#addButton:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/add_Unselected.png);
                }}
                QPushButton#addButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/add_Selected.png)
                }}

                QPushButton#deleteButton{{
                    border: 5px solid {buttonUnselectedColor};
                    border-radius: 30px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Checkmark_Unselected.png);
                }}
                QPushButton#deleteButton:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Checkmark_Unselected.png);
                }}
                QPushButton#deleteButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Checkmark_Selected.png);
                }}

                QComboBox{{
                    font-weight: bold;
                    background-color: transparent;
                    border: 2px solid;
                    border-radius: 5px;
                }}

                QMessageBox{{
                    font-weight: bold;
                    background-color: {frameBackgroundColor};
                    border: 5px solid {frameBorderColor};
                }}
        """  

if __name__ == '__main__':
    app = QApplication(sys.argv)
    temp = SettingMenu()
    temp.show()
    sys.exit(app.exec())    