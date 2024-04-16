The first version - 2024/3/12: added the basic display of desktop pet image and a tray menu for quit and hide.

2024/3/19
    Trying to add a wandering function which allows pet to move around the desktop every once a while. However, there isn't a inherited function to do so, so I need to write one myself. I initially created a movement loop in in a function called wandering, then realizing it will pause the main loop. I need to put the wandering function in a sub thread. Here are two posts I'm referencing:
    post1 = https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/
    post2 = https://realpython.com/python-pyqt-qthread/
    It seems like the approach in post1 no longer functions. Yet, the approach in post2 is very complicated... I'm having trouble simply understanding it. I think I'll have to rest a little...
    Ok, after... three hours? I got the random movement function working. The multi-threading function is quite interesting to be honest(considering all the shit that can pop up during development). Luckily, I haven't met any problem like race condition, deadlock, livelock, or starvation... However, I occasionally get "QThread: Destroyed while thread is still running" error. Since it's a run time error, I can't really trace its source... So far, the most reasonable explanation is that a _wanderingThread takes longer to execute than the cool down interval. While the prior thread is still executing, the latter thread seize its pointer "self._wanderingThread", causing it to be destoried by python. 
    I'll set the cool down interval longer, and shorten the execution time. We'll see how it goes.

2024/3/20
    I add a speech bubble function to Desktop pet, which follows the pet as it moves and change position when hitting the extreme. Having some experience, I used multi-threading again. This time was more fluent, except that I initially wanted to create gui on another thread orz. It took me a while to figure out that I can't do that.
    Some how, QLabel doesn't display when being a subwindow on its own, so my speech bubble inherited QMainWindow instead of QLabel. This created a lot of fuzz. It took me some effort to figure out how to display only the Qlabel while keep QMainWindow transparent. Then the placing of the speech bubble is off. 
    Istead of displayed in the middle, it skewed right. At first, I thought my calculation for it was off. After 20 minutes of verification, I realize the the problem was the size of my label. Somehow the length of the displayed label is like 700px but its QSize.width() remained 200px. I tried several ways to fix it without success. It was then I recalled that the QLabel was in the QMainwindow. Resizing QLabel won't help if the size of QMainwindow remain fixed. 
    I add a line to code to resize QMainwindow after fill QLabel with text. The bug was fixed. 
    THIS SIFT TOOK ME 2 F**KING HOURS!

2024/3/21
    Enabled Desktop Pet to read from local files for dialogue, and also by accident solved "QThread: Destroyed while thread is still running" error. All I really needed to do is to pass in the desktop pet as the parent for QThread initializations. WHy didn't I thought about it before?

    For my Calendar part of the program, I surprising found that PyQt5 has a calendar class it self called QCalendarWidget. Here are some examples for it: 
    GKG = https://www.geeksforgeeks.org/pyqt5-qcalendarwidget/

    Before proceeding to the next goal, I added resize smaller/bigger functions to Desktop Pet, this is probably the last function about the pet itself before I complete the calendar sections of it.

2024/3/22
    Made speech bubbles dynamically adjusts to the size of Desktop Pet.
    Add utf-8 encoding to file reading
    Fixed the possibility of crashing due to speech bubbles (probably)

2024/3/25
    Begining to write the calendar function. I slightly changed my mind though. Rather than writting a calendar that sets a time to notice user about something, I want let user set the notice interval of different groups of dialog.
    I call the gui interface I'm developing now "SettingBox" because it also incorporates the settings of desktop pet. It is in a separate file for now, I'll integrate it into the main file later... maybe not. It's too long to be integerated.
    Oh, I also create a folder for the ui icons and future config files for better appearence.


2024/3/26
    the format for setting log is:
    ["Movement interval starts", "Movement interval ends", "language"]

    Note: there are alogrithms detecting mouse movement known as hud, which tracts the movement of mouse.

2024/4/10
    I'm beginning to write the physic simulation of DesktopPet today.
    First about, I need to get the user mouse movement speed, which can be easily accompolished by subtracting self._previous_drag_pos.x() from eventPos.x(). They are both used for original movement calculation.

    The end goal is to get the Δθ (change in angle) of the pet in response to the user movement. Using the circular movement of kinomatic equation, we have:

        Δθ = (wi)t + (1/2)(a)(t**2)
    
    To find t (time), we can use momentum impluse equation:

        Iw = τt = ΔL
        t = Iw/τ
    
    Since we are in a virtual environment, I can assume that mouse applies a constant torque τ upon desktop pet, and the moment of inertia I is all constant. Of course, this is based on the premise that the pivot (where user clicks) is fixed.

    I realized that I can actually simulate the pendulem without using momentum impulse equation. In equation Δθ = (wi)t + (1/2)(a)(t**2), acceleration (a) is the gravity. I can then easily derive Δθ with this equation.
    dx = 90 if dx > 90 else dx (dx is the mouse speed, the fastest it can get is 90 pixel/frame)
    t = 1
    a = -0.5
    dTheta = dx*t + 0.5*a*(t)**2 (The range of dTheta is [0.75, 89.75])
    pic = QPixmap('normalState/Drag.gif').transformed(QTransform().rotate(dTheta))
    self.petLabel.setPixmap(pic)
    
    This is my first attempt in simulating pendulem, and of course, it failed.
    The biggest problem with it is that I assume use grab pet by middle top, but the rotation center of QTransform is top left.
    Second, the alogrithm isn't smooth enough. There are significant lag in rotation. 

2024/4/11
    I managed to fixed the center of rotation problem by using the translate function of QTransform. Translate shifts the center of rotation alone the plane. The lag problem was also addressed by adjusting the frame rate. 
    
    As I was developing, I realized that sometimes the rotated image will go out of the boundary of display area, leading to some of it getting corped. I tried to auto adjust the size of the display area, but that messed up the display posiiton of speechbubble... In the end, I had to add an extra layer of margin to the pet, and changed every single lines of code related to movement and scaling....SO FUN.

2024/4/13
    I managed to let pet rotate on centering the point where user clicks it. However, once again I don't understand the code I wrote:

    1 center = (self.size().width()//2, self.size().height()//2) #Finding the center coordinate of of the pet 
    2 xdiff = -(center[0] - self._drag_pos.x()) #calculate of width of triangle, by default, the positive x in math corresponds to negative x in the program, so I reversed the sign for calculation.
    4 ydiff = center[1] - self._drag_pos.y() #calculated the height of the triangle

    5 if xdiff == 0: xdiff = 1 #Prevent divided by 0 error (Horizontal slop)
    6 grabAngle = atan(ydiff/xdiff) * (180/pi) #Get the radiant of the angle and convert it to degrees

    7 QTransform().rotate(grabAngle-90 if xdiff>0 else grabAngle+90).rotate(dTheta) #Transform

    Line 7 is what I failed to understand.
    Here is my origin code:

    7 QTransform().translate(center[0], center[1]).rotate(grabAngle-90 if xdiff>0 else grabAngle+90).rotate(dTheta).translate(-center[0], -center[1])

    You see, digital images doesn't use the rectangle coordinate plane we're familar with, rather, the origin is on the top lett, and moving downward corresponds to positive y. That is to say, when perform matrix operations, I need to translate the origin of the image center to the coordinate center for the rotation to work properly. That is accompolished by: .translate(center[0], center[1]).
    Rotate the image by granAngle to simulate the effect of grabing at an angle. 
    Rotate the image by the dTheta to simulate the effect of pet swing around.
    Lastly, move translate the image center back to where it should be.

    Yet, the thing worked without the translation of the center. Very, very, perplexing.

2024/4/16
    Got this bastard solved!
    I tried a different approach during this period: Linear algebra.
    Since I can't let pet rotate on where the user clicks it, I can shift the point corresponding to the click point to clikc point after rotation. 
    
    Say if I know click point A = (233, 233) will shift to B = (114, 514) after rotation, I can shift the whole grahic by a distance of B - A to move B to where A is.
    This is the basic of translation in linear algebra.
    To rotate a point, we can use rotation matrix:
    |cosθ -sinθ|
    |sinθ  cosθ|
    And then multiple it to the (x, y) coordinate to be rotated:
    |cosθ -sinθ| \/ |x| = xcosθ - ysinθ = x'
    |sinθ  cosθ| /\ |y| = xsinθ + ycosθ = y'
    (x', y') is the resulting coordinate of rotation. 
    During rotation, center of rotation is an importation consideration. If the center of rotated shape isn't on the origin, it will be rotated to another quadrant instead by center. So it's necessar to shift the center of the shape to origin before rotation:

        1 shiftDistance = QPoint(self.size().width()//2, self.size().height()//2) + self.pos()
        2 clickPointT = eventPos - shiftDistance
        3 xPrime = clickPointT.x()*cos(angle) - clickPointT.y()*sin(angle)
        4 yPrime = clickPointT.x()*sin(angle) + clickPointT.x()*cos(angle)
        5 clickPointTR = QPoint(int(xPrime), int(yPrime))
        6 Find the distance from topleft rotated to it's origin
        7 shiftDistance2 = eventPos - clickPointTR 
        8 topLeftTT = topLeftT+shiftDistance2
        9 self.move(topLeftTT)

    This didn't worked. 
    The pet was always distant from the cursor, and somethings went off screen.
    After a long test with controlled variables, I figured out that the problem wasn't with my calculation or linear algebra skill. The root cause was that the rotation to the pet perfomed by QTransformation.rotation(angle) is different form the rotation matrix.
    In my note two days ago, I wrote that translation didn't matter in rotation. I was wrong. When perform QTransformation.rotation with the default rotation center, the image was actually rotated to another quadrant. Yet, we still got the image displayed. 
    Image the rectangle displaying image a camera. When imaged being rotated to another quadrant, it follows it to the quadrant. That's why we sill got the desired image without the need to translate the center of rotation. 
    This change is the 'camera position' is pretty much unpredictible, i.e. I don't know how to, so I needed another way to do it. 

    Luckily, as I swam through stackoverflow threads, I noticed a function called map(). QTransformation.map() takes in an set of coordinate on the origination image, then return the coordinate corresponds to the same point on the transformed image. 
    The functionality of map() was exactly what I looked for. After all, all I want is that the pet rotated around the point user clicked so that the ration doens't create a gap between cursor and image. 
    With map(), I can feed in the point cursor clicked and obtain the same point after the rotation. Perfect!
        1 transformer = QTransform().translate(self.size().width()/2, self.size().height()/2).rotate(self.grabAngle+15).translate(-self.size().width()/2, -self.size().height()/2)
        2 new_drag_pos = transformer.map(self._drag_pos)
        3 self._drag_pos = new_drag_pos
    self._drag_pos recorded the point user clicked. After replacing it with the new coordinate, the image automatically translate to the cursor. 

    A strange thing is, using the same angle, self.grabAngle, used to rotated pet to find new_drag_pos will create a gap between cursor and image. However, by adding 15 to the angle eliminates the gap. 
    I have no idea why this happens...