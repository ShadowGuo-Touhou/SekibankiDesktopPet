import os , sys, random, time, json
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QWidget

#Bubble is for displaying the 
class Bubble(QWidget):
    changed = pyqtSignal(int)

    def __init__(self, name):
        super().__init__()
        self.Name = name       

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
        self.initReadSetting()

        self.initFrame()
        self.initSetting()
        self.initSpeechSetting()
        self.initBubbleConfigPage()
        self.switchSettingPage()

        self.styleSheetSet()

        self.setStyleSheet(self.StyleSheet)

#Read settings and dialogs-------------------------------------------------------------------------------
    def initReadSetting(self):
        #Load config file
        try:
            with open('assets/Settings/config.json') as s:
                self.SETTING = json.load(s)
        except Exception as e:
            print(e)
            self.warning.emit(str(e))
            self.SETTING = {'start':20, 'end':300, 'language': 0, "clickDialogFrequency": 50, "speechBubbleOpacity": 0.5}
        #load language, since there ain't really much text, I'll just embed language file in the code.
        if self.SETTING['language'] == 0:
            self.LANGUAGE = {"moveInterval": "Movement Interval:", "to": "to", "seconds": "seconds.", "language": "language",'dialogInterval': 'Dialog Interval:', "illegalInputWarning": "Not gonna work, check your inputs, dummy.", "successfulSave": "Got it. I'll make the change after restart.", "newBubble":"Enter the name for new dialog group:", 'newBubble2': "Enter the content of dialog:", 'deleteBubble': "Confirm deleting", "error": "Error encountered:", "time": "Duration:", "color":"Speech bubble color:", 'tooManyClickWarning': "Hey! don't click so many times!\nMy creator didn't handle exceptions properly...", "clickDialogFrequency":"Click dialog display chance:", "speechBubbleOpacity":"Speechbubble opacity: "}
        else:
            self.LANGUAGE = {'moveInterval': "移动时间间隔:", 'to': '到', 'seconds': '秒。', 'language': '语言', 'dialogInterval': '对话出现间隔：','illegalInputWarning': '参数错误，检查一下啦，笨蛋。', 'successfulSave': '知道啦，重启时改正~', 'newBubble': '请输入新对话列表的名称：', 'newBubble2': "请输入对话内容：",'deleteBubble': '确认删除', "error":"遭遇错误：", 'time': "持续时间：", "color":"对话泡颜色：", "tooManyClickWarning": "喂！少点几下哦！\n作者没做Exception Handling啦...", "clickDialogFrequency":"点击对话出现概率: ", "speechBubbleOpacity":"对话泡透明度："}

            
    def loadDialog(self):
        #Load dialogues and safe them in a dictionary
        self.DIALOGS = {}
        dialogs = os.listdir('assets/Dialogs')
        try:
            for x in dialogs:
                with open(r'assets/Dialogs/'+x) as s:
                    self.DIALOGS[x.split('.')[0]] = json.load(s)
        except Exception as e:
            print(e)
            self.warning.emit(f"{self.LANGUAGE['error']} {e}")
        if "clickDialog" not in self.DIALOGS:
            self.DIALOGS['clickDialog'] = {'color':'white', 'start':30, 'end': 200, 'time':5, 'id':'clickDialog', 'dialog':[]}

        #create a container for speechbubbles
        speechBubbleContainer = QWidget()
        speechBubbleContainer.setStyleSheet("background-color: transparent")
        speechBubbleContainerLayout = QVBoxLayout()
        speechBubbleContainerLayout.setContentsMargins(0,5,0,0)
        speechBubbleContainer.setLayout(speechBubbleContainerLayout)
        
        #Create speech bubbles for each dialog
        for dialog in self.DIALOGS.values():
            #the body of bubble
            bubble = QWidget()
            bubble.setFixedSize(495, 100)
            bubble.setObjectName('bubble')
            bubbleLayout = QHBoxLayout()
            bubble.setLayout(bubbleLayout)
            #The id label of dialog
            name = QLabel()
            name.setMinimumWidth(200)
            name.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            name.setText(dialog['id'])
            bubbleLayout.addWidget(name)
            #Add some fillings
            bubbleLayout.addStretch(0)
            #The buttons
            #manage button
            manage = self.NamedButton()
            manage.setFixedSize(50, 50)
            manage.setObjectName('manageButton')
            manage.setText(dialog['id'])
            manage.clicked.connect(lambda id: self.switchBubbleConfigPage(id))
            bubbleLayout.addWidget(manage)
            #Delete button
            delete = self.NamedButton()
            delete.setText(dialog['id'])
            delete.setFixedSize(50, 50)
            delete.setObjectName("deleteButton")
            delete.clicked.connect(lambda id:self.speechBubbleDelete(id))
            bubbleLayout.addWidget(delete)
            bubbleLayout.addSpacing(10)
            
            speechBubbleContainerLayout.addWidget(bubble)
        return speechBubbleContainer
    
    class NamedButton(QPushButton):
        clicked = pyqtSignal(str)
        def __init__(self):
            super().__init__()
        def setText(self, a0):
            self.text = a0
        def mousePressEvent(self, e):
            self.clicked.emit(self.text)
            super().mousePressEvent(e)
    
    def speechBubbleDelete(self, id):
        self.deleteBox = QWidget(self)
        self.deleteBox.setObjectName('questionBox')
        self.deleteBox.setFixedSize(300, 200)
        self.deleteBox.move(150, 150)
        #create a top layout
        questionBoxLayout = QGridLayout()
        self.deleteBox.setLayout(questionBoxLayout)
        #create places to enter name
        message = QLabel(self.LANGUAGE['deleteBubble'])
        message.setAlignment(Qt.AlignCenter)
        speechSettingNameBox = QLabel(id)
        speechSettingNameBox.setAlignment(Qt.AlignCenter)
        speechSettingNameBox.setWordWrap(True)
        questionBoxLayout.addWidget(message, 0, 0, 1, 3)
        questionBoxLayout.addWidget(speechSettingNameBox, 1, 0, 1, 3)
        #create buttons
        #confirm
        questionBoxButtonLayout = QHBoxLayout()
        confirmButtom = QPushButton()
        confirmButtom.setFixedSize(60, 60)
        confirmButtom.setObjectName('confimButton')
        confirmButtom.clicked.connect(lambda: self.speechBubbleDelete2(id))
        questionBoxButtonLayout.addWidget(confirmButtom)
        #cancel
        cancelButton = QPushButton()
        cancelButton.setFixedSize(60, 60)
        cancelButton.setObjectName('cancelButton')
        cancelButton.clicked.connect(self.deleteBox.close)
        questionBoxButtonLayout.addWidget(cancelButton)

        questionBoxLayout.addLayout(questionBoxButtonLayout, 2, 0, 2, 3)
        self.deleteBox.show()

    #Delete the choosen bubble
    def speechBubbleDelete2(self, id):
        #Try delete it, or send error
        try:
            os.remove(f"assets/Dialogs/{id}.json")
            
        except Exception as e:
            self.warning.emit(self.LANGUAGE['tooManyClickWarning'])
            print(e)
        self.speechBubbleReload()
        self.deleteBox.close()

    def speechBubbleReload(self):
        self.speechBubbleScrollArea.setWidget(self.loadDialog())

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
        settingPageLayout.setContentsMargins(15,0,15, 20)
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
        settingPageLayout.addLayout(movementIntervalLayout)

        #add click dialog frequency
        clickDialogLayout = QHBoxLayout()
        clickDialogLayout.addWidget(QLabel(self.LANGUAGE['clickDialogFrequency']))
        clickDialogLayout.addStretch(0)
        self.clickDialogFrequency = QLineEdit()
        self.clickDialogFrequency.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9][0]")))
        self.clickDialogFrequency.setText(str(self.SETTING['clickDialogFrequency']))
        self.clickDialogFrequency.setMaximumWidth(50)
        clickDialogLayout.addWidget(self.clickDialogFrequency)
        clickDialogLayout.addWidget(QLabel("%"))
        settingPageLayout.addLayout(clickDialogLayout)

        #Add speechbubble Opacity
        speechBubbleOpacityLayout = QHBoxLayout()
        speechBubbleOpacityLayout.addWidget(QLabel(self.LANGUAGE['speechBubbleOpacity']))
        speechBubbleOpacityLayout.addStretch(0)
        self.speechBubbleOpacity = QLineEdit()
        self.speechBubbleOpacity.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9][0]")))
        self.speechBubbleOpacity.setText(str(int(self.SETTING['speechBubbleOpacity']*100)))
        self.speechBubbleOpacity.setMaximumWidth(50)
        speechBubbleOpacityLayout.addWidget(self.speechBubbleOpacity)
        speechBubbleOpacityLayout.addWidget(QLabel("%"))
        settingPageLayout.addLayout(speechBubbleOpacityLayout)

        #add language selection
        languageLayout = QHBoxLayout()
        languageLayout.addWidget(QLabel(self.LANGUAGE['language']))
        languageLayout.addStretch(0)
        self.languageChoice = QComboBox()
        self.languageChoice.addItem("English")
        self.languageChoice.addItem("中文")
        self.languageChoice.setFixedWidth(100)
        self.languageChoice.setCurrentIndex(self.SETTING['language'])
        languageLayout.addWidget(self.languageChoice)
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
        
        start = int(self.movementIntervalStart.text())
        end = int(self.movementIntervalEnd.text())

        if start>= end:
            self.warning.emit(self.LANGUAGE['illegalInputWarning'])
            return
        
        clickDialogFrequency = int(self.clickDialogFrequency.text())
        speechBubbleOpacity = int(self.speechBubbleOpacity.text())
        if clickDialogFrequency > 100: clickDialogFrequency = 100
        if speechBubbleOpacity > 100: speechBubbleOpacity = 100

        language = self.languageChoice.currentIndex()
        with open('assets/Settings/config.json', 'w+') as s:
            json.dump({'start': start, 'end': end, 'language': language, 'clickDialogFrequency':clickDialogFrequency, 'speechBubbleOpacity':speechBubbleOpacity/100}, s)
        #emit signal
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
        self.speechBubbleScrollArea = QScrollArea()
        self.speechBubbleScrollArea.resize(500,400)
        speechSettingPageMinorLayout.addWidget(self.speechBubbleScrollArea, 0, 0, 4, 4)
        self.speechBubbleScrollArea.setObjectName("speechBubbleScrollArea")
        #Hide scrollbar
        self.speechBubbleScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.speechBubbleScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        #set widget
        self.speechBubbleScrollArea.setWidget(self.loadDialog())

        #Create a layout to hold options.
        speechBubbleControllerLayout = QVBoxLayout()

        speechSettingPageMinorLayout.addLayout(speechBubbleControllerLayout, 0,4, 4, 1)
        #Create option buttons
        #Add more speech slot
        addButton = QPushButton()
        addButton.setObjectName('addButton')
        addButton.setFixedSize(60,60)
        addButton.clicked.connect(self.speechSettingGetName)
        speechBubbleControllerLayout.addWidget(addButton)

    #The page asking for uer input of speech bubble name
    def speechSettingGetName(self):
        self.questionBox = QWidget(self)
        self.questionBox.setObjectName('questionBox')
        self.questionBox.setFixedSize(300, 200)
        self.questionBox.move(150, 150)
        #create a top layout
        questionBoxLayout = QGridLayout()
        self.questionBox.setLayout(questionBoxLayout)
        #create places to enter name
        message = QLabel(self.LANGUAGE['newBubble'])
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        self.speechSettingNameBox = QLineEdit()
        questionBoxLayout.addWidget(message, 0, 0, 1, 3)
        questionBoxLayout.addWidget(self.speechSettingNameBox, 1, 0, 1, 3)
        #create buttons
        #confirm
        questionBoxButtonLayout = QHBoxLayout()
        confirmButtom = QPushButton()
        confirmButtom.setFixedSize(60, 60)
        confirmButtom.setObjectName('confimButton')
        questionBoxButtonLayout.addWidget(confirmButtom)
        confirmButtom.clicked.connect(self.speechBubbleCreate)
        #cancel
        cancelButton = QPushButton()
        cancelButton.setFixedSize(60, 60)
        cancelButton.setObjectName('cancelButton')
        cancelButton.clicked.connect(self.questionBox.close)
        questionBoxButtonLayout.addWidget(cancelButton)

        questionBoxLayout.addLayout(questionBoxButtonLayout, 2, 0, 2, 3)

        self.questionBox.show()
    #confirm the name
    def speechBubbleCreate(self):
        name = self.speechSettingNameBox.text()
        newBubble = {'color':'white', 'start':30, 'end': 200, 'time':5, 'id':name, 'dialog':[]}
        with open(f'assets/Dialogs/{name}.json', 'w+') as s:
            json.dump(newBubble, s)
        self.questionBox.close()
        #reload the list
        self.speechBubbleReload()
        
#DIalog configuration page------------------------------------------------------
    #Switch to bubble config page, initialize page with corresponding dialog
    def switchBubbleConfigPage(self, id):
        #Set Id for buttons to return
        self.bubbleTitle.setText(id)
        self.addBubble.setText(id)
        self.bubblePallette.setText(id)
        self.bubbleConfirm.setText(id)
        #fill configurations for the bubble
        self.bubbleTimeStart.setText(str(self.DIALOGS[id]['start']))
        self.bubbleTimeEnd.setText(str(self.DIALOGS[id]['end']))
        self.bubbleColor.setStyleSheet(f"background-color:{self.DIALOGS[id]['color']}")
        self.bubbleDuration.setText(str(self.DIALOGS[id]['time']))

        #Generate the bubble list for self.bubbleContainer
        self.bubbleContainer.setWidget(self.bubbleListGenerate(id))
        #Switch to the layout
        self.stackLayout.setCurrentIndex(2)

    #configurate dialogues
    def initBubbleConfigPage(self):
        #Create a new stack page 
        bubbleConfig = QWidget()
        self.stackLayout.addWidget(bubbleConfig)
        bubbleConfigLayout = QGridLayout()
        bubbleConfig.setLayout(bubbleConfigLayout)

        #title
        self.bubbleTitle = QLabel()
        self.bubbleTitle.setAlignment(Qt.AlignCenter)
        bubbleConfigLayout.addWidget(self.bubbleTitle, 0, 0, 1, 5)

        #Get time interval
        bubbleTimeLayout = QHBoxLayout()
        bubbleTimeLayout.addSpacing(10)
        #Start
        bubbleTimeLayout.addWidget(QLabel(self.LANGUAGE['dialogInterval']))
        bubbleTimeLayout.addStretch(0)
        self.bubbleTimeStart = QLineEdit()
        self.bubbleTimeStart.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9][0-9][0-9]")))
        bubbleTimeLayout.addWidget(self.bubbleTimeStart)
        bubbleTimeLayout.addWidget(QLabel(self.LANGUAGE['to']))
        self.bubbleTimeStart.setFixedWidth(50)
        #End
        self.bubbleTimeEnd = QLineEdit()
        self.bubbleTimeEnd.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9][0-9][0-9]")))
        bubbleTimeLayout.addWidget(self.bubbleTimeEnd)
        bubbleTimeLayout.addWidget(QLabel(self.LANGUAGE['seconds']))
        self.bubbleTimeEnd.setFixedWidth(50)
        bubbleTimeLayout.addSpacing(10)
        bubbleConfigLayout.addLayout(bubbleTimeLayout, 1, 0, 1, 5)

        #Time
        bubbleLiveLayout = QHBoxLayout()
        bubbleLiveLayout.addSpacing(10)
        bubbleLiveLayout.addWidget(QLabel(self.LANGUAGE['time']))
        bubbleLiveLayout.addStretch(0)
        self.bubbleDuration = QLineEdit()
        self.bubbleDuration.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9]")))
        self.bubbleDuration.setFixedWidth(50)
        bubbleLiveLayout.addWidget(self.bubbleDuration)
        bubbleLiveLayout.addWidget(QLabel(self.LANGUAGE['seconds']))
        bubbleLiveLayout.addSpacing(10)
        bubbleConfigLayout.addLayout(bubbleLiveLayout, 2, 0, 1, 5)

        #Color
        bubbleColorLayout = QHBoxLayout()
        bubbleColorLayout.addSpacing(10)
        bubbleColorLayout.addWidget(QLabel(self.LANGUAGE['color']))
        bubbleColorLayout.addStretch(0)
        self.bubbleColor = QLabel()
        self.bubbleColor.setObjectName("colorDisplay")
        self.bubbleColor.setFixedWidth(50)
        bubbleColorLayout.addWidget(self.bubbleColor)
        bubbleColorLayout.addSpacing(10)
        bubbleConfigLayout.addLayout(bubbleColorLayout, 3, 0, 1, 5)
        
        #container Area
        self.bubbleContainer = QScrollArea()
        self.bubbleContainer.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bubbleContainer.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bubbleContainer.setObjectName('speechBubbleScrollArea')
        temp = QWidget()
        self.bubbleContainer.setWidget(temp)
        bubbleConfigLayout.addWidget(self.bubbleContainer, 4,0,7,4)
        
        #button area
        bubbleButtonContainer = QVBoxLayout()
        bubbleButtonContainer.addStretch(0)
        #Add dialog button
        self.addBubble = self.NamedButton()
        self.addBubble.setFixedSize(60, 60)
        self.addBubble.setObjectName('addButton')
        self.addBubble.clicked.connect(lambda id: self.bubbleGetContent(id))
        bubbleButtonContainer.addWidget(self.addBubble)
        #Dialog color button
        self.bubblePallette = self.NamedButton()
        self.bubblePallette.setFixedSize(60, 60)
        self.bubblePallette.setObjectName('paletteButton')
        self.bubblePallette.clicked.connect(lambda id: self.bubbleGetColor(id))
        bubbleButtonContainer.addWidget(self.bubblePallette)
        #Confirm button 
        self.bubbleConfirm = self.NamedButton()
        self.bubbleConfirm.setFixedSize(60,60)
        self.bubbleConfirm.setObjectName('confimButton')
        self.bubbleConfirm.clicked.connect(lambda x: self.bubbleSave(x))
        bubbleButtonContainer.addWidget(self.bubbleConfirm)
        
        bubbleButtonContainer.addStretch(0)
        bubbleConfigLayout.addLayout(bubbleButtonContainer, 4,4, 7, 1)


    #Generate the list of dialogs
    def bubbleListGenerate(self, id):
        #This QWidget is the container that holds individual dialogs
        BubbleContainer = QWidget()
        BubbleContainer.setStyleSheet("background-color: transparent")
        BubbleContainerLayout = QVBoxLayout()
        BubbleContainerLayout.setContentsMargins(0,5,0,0)
        BubbleContainer.setLayout(BubbleContainerLayout)
        
        #Create speech bubbles for each dialog
        for dialog in self.DIALOGS[id]['dialog']:
            #Call upon self.bubbleGenerate to create a signle instance of bubble
            BubbleContainerLayout.addWidget(self.bubbleGenerate(id, dialog))
        #Return the QWidget for self.bubbleContainer to hold
        return BubbleContainer
    
    #Generate a signle bubble
    def bubbleGenerate(self, id, dialog):
        #the body of bubble
        bubble = QWidget()
        bubble.setMinimumSize(495, 50)
        bubble.setObjectName('bubble2')
        bubbleLayout = QHBoxLayout()
        bubble.setLayout(bubbleLayout)
        #The id label of dialog
        content = QLabel()
        content.setMinimumWidth(400)
        content.setAlignment(Qt.AlignVCenter)
        content.setText(dialog)
        content.setWordWrap(True)
        bubbleLayout.addWidget(content)
        #Add some fillings
        bubbleLayout.addStretch(0)
        #The button
        #Delete button
        delete = self.NamedButton()
        delete.setText(f"{dialog}!@#$%^&*&^%$#@!{id}")
        delete.setFixedSize(50, 50)
        delete.setObjectName("deleteButton")
        bubbleLayout.addWidget(delete)
        bubbleLayout.addSpacing(10)
        delete.clicked.connect(lambda x: self.bubbleDelete(x))
        #Return the instance of bubble
        return bubble
    
    #Add new bubble
    def bubbleGetContent(self, id):
        self.questionBox = QWidget(self)
        self.questionBox.setObjectName('questionBox')
        self.questionBox.setFixedSize(300, 200)
        self.questionBox.move(150, 150)
        #create a top layout
        questionBoxLayout = QGridLayout()
        self.questionBox.setLayout(questionBoxLayout)
        #create places to enter name
        message = QLabel(self.LANGUAGE['newBubble2'])
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        self.speechSettingNameBox = QLineEdit()
        self.speechSettingNameBox.setMinimumHeight(30)
        questionBoxLayout.addWidget(message, 0, 0, 1, 3)
        questionBoxLayout.addWidget(self.speechSettingNameBox, 1, 0, 1, 3)
        #create buttons
        #confirm
        questionBoxButtonLayout = QHBoxLayout()
        confirmButtom = QPushButton()
        confirmButtom.setFixedSize(60, 60)
        confirmButtom.setObjectName('confimButton')
        questionBoxButtonLayout.addWidget(confirmButtom)
        confirmButtom.clicked.connect(lambda: self.bubbleCreate(id))
        #cancel
        cancelButton = QPushButton()
        cancelButton.setFixedSize(60, 60)
        cancelButton.setObjectName('cancelButton')
        cancelButton.clicked.connect(self.questionBox.close)
        questionBoxButtonLayout.addWidget(cancelButton)

        questionBoxLayout.addLayout(questionBoxButtonLayout, 2, 0, 2, 3)

        self.questionBox.show()
    #confirm the name
    def bubbleCreate(self, id):
        self.questionBox.close()
        content = self.speechSettingNameBox.text()
        self.DIALOGS[id]['dialog'].append(content)
        self.bubbleReload(id)


    #Delete the dialog then re-generate the list
    def bubbleDeleteDialog(self, stream):
        self.deleteBox.close()
        splited = stream.split('!@#$%^&*&^%$#@!')
        try:
            self.DIALOGS[splited[1]]['dialog'].remove(splited[0])
        except:
            self.warning.emit(self.LANGUAGE['tooManyClickWarning'])
        self.bubbleReload(splited[1])

        
    #This window confirms if the user want to delete the dialog
    def bubbleDelete(self, id):
        self.deleteBox = QWidget(self)
        self.deleteBox.setObjectName('questionBox')
        self.deleteBox.setFixedSize(300, 200)
        self.deleteBox.move(150, 150)
        #create a top layout
        questionBoxLayout = QGridLayout()
        self.deleteBox.setLayout(questionBoxLayout)
        #create places to enter name
        message = QLabel(self.LANGUAGE['deleteBubble'])
        message.setAlignment(Qt.AlignCenter)
        questionBoxLayout.addWidget(message, 0, 0, 1, 3)
        #create buttons
        #confirm
        questionBoxButtonLayout = QHBoxLayout()
        confirmButtom = QPushButton()
        confirmButtom.setFixedSize(60, 60)
        confirmButtom.setObjectName('confimButton')
        confirmButtom.clicked.connect(lambda: self.bubbleDeleteDialog(id))
        questionBoxButtonLayout.addWidget(confirmButtom)
        #cancel
        cancelButton = QPushButton()
        cancelButton.setFixedSize(60, 60)
        cancelButton.setObjectName('cancelButton')
        cancelButton.clicked.connect(self.deleteBox.close)
        questionBoxButtonLayout.addWidget(cancelButton)

        questionBoxLayout.addLayout(questionBoxButtonLayout, 1, 0, 2, 3)
        self.deleteBox.show()

    #Reload the list of bubbles
    def bubbleReload(self, id):
        self.bubbleContainer.setWidget(self.bubbleListGenerate(id))

    #save all the changes to the dialog
    def bubbleSave(self, id):
        #get the start, end, and duration
        start = int(self.bubbleTimeStart.text())
        end = int(self.bubbleTimeEnd.text())
        duration = int(self.bubbleDuration.text())
        #Update the dictionary
        self.DIALOGS[id]['start'] = start
        self.DIALOGS[id]['end'] = end
        self.DIALOGS[id]['time'] = duration
        #Raise flag if start time greater than end
        if start >= end:
            self.warning.emit(self.LANGUAGE['illegalInputWarning'])
            return
        #return the the previous window and write the change to file
        self.stackLayout.setCurrentIndex(1)
        with open(r'assets/Dialogs/'+id+".json", 'w+') as s:
            json.dump(self.DIALOGS[id], s)

        
    #Change bubble color
    def bubbleGetColor(self, id):
        #Create a color dialog for user to pick color
        bubbleColor = QColorDialog()
        bubbleColor.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        bubbleColor.setCurrentColor(QColor(self.DIALOGS[id]['color']))
        bubbleColor.exec()
        #Get name directly returns the hex for the color
        color = bubbleColor.currentColor().name()
        self.DIALOGS[id]['color'] = color
        self.bubbleColor.setStyleSheet(f"background-color:{color}")

    
    #Allow desktop to grab the dialog list
    def getDialog(self):
        return self.DIALOGS
    

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
        if __name__ == '__main__':
            sys.exit()
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
        frameBorderColorLight = 'gray'
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
                    border: 3px solid {buttonUnselectedColor};
                    border-radius: 25px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Trashcan_Unselected.png);
                    color: transparent;
                }}
                QPushButton#deleteButton:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Trashcan_Unselected.png);
                }}
                QPushButton#deleteButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Trashcan_Selected.png);
                }}
                QPushButton#manageButton{{
                    border: 3px solid {buttonUnselectedColor};
                    border-radius: 25px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Gear_Unselected.png);
                    color: transparent;
                }}
                QPushButton#manageButton:hover{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Gear_Unselected.png);
                }}
                QPushButton#manageButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Gear_Selected.png);
                }}
                
                QComboBox{{
                    font-weight: bold;
                    background-color: transparent;
                    border: 2px solid;
                    border-radius: 5px;
                }}
                QLineEdit{{
                    font-weight: bold;
                    background-color: {frameBackgroundColor};
                    border: 2px solid {frameBorderColor};
                    border-radius: 10px
                }}

                QWidget#questionBox{{
                    font-weight: bold;
                    background-color: {frameBackgroundColor};
                    border: 5px solid {frameBorderColor};
                    border-radius: 20px;
                }}

                QPushButton#cancelButton{{
                    border: 5px solid {buttonUnselectedColor};
                    border-radius: 30px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/X_Unselected.png);
                }}
                QPushButton#cancelButton:hover{{
                    image: url(assets/UI/X_Unselected.png);
                    border-color: {buttonSelectedColor};
                }}
                QPushButton#cancelButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/X_Selected.png);
                }}

                QWidget#bubble{{
                    border: 5px solid {frameBorderColorLight};
                    border-radius: 50px;
                }}
                QWidget#bubble:hover{{
                    border-color: {frameBorderColor};
                }}

                QPushButton#paletteButton{{
                    border: 5px solid {buttonUnselectedColor};
                    border-radius: 30px;
                    background-color: {buttonBackgroundColor};
                    image: url(assets/UI/Palette_Unselected.png);
                }}
                QPushButton#paletteButton:hover{{
                    image: url(assets/UI/Palette_Unselected.png);
                    border-color: {buttonSelectedColor};
                }}
                QPushButton#paletteButton:pressed{{
                    border-color: {buttonSelectedColor};
                    image: url(assets/UI/Palette_Selected.png);
                }}

                QLabel#colorDisplay{{
                    border: 5px double black;
                    border-radius: 10px
                }}

                QWidget#bubble2{{
                    border: 5px solid {frameBorderColorLight};
                    border-radius: 25px;
                }}
                QWidget#bubble2:hover{{
                    border-color: {frameBorderColor};
                }}

        """  

if __name__ == '__main__':
    app = QApplication(sys.argv)
    temp = SettingMenu()
    temp.show()
    sys.exit(app.exec())    