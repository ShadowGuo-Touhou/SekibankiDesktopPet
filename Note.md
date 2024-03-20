The first version - 2024/3/12: added the basic display of desktop pet image and a tray menu for quit and hide.

2024/3/19
    Trying to add a wandering function which allows pet to move around the desktop every once a while. However, there isn't a inherited function to do so, so I need to write one myself. I initially created a movement loop in in a function called wandering, then realizing it will pause the main loop. I need to put the wandering function in a sub thread. Here are two posts I'm referencing:
    post1 = https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/
    post2 = https://realpython.com/python-pyqt-qthread/
    It seems like the approach in post1 no longer functions. Yet, the approach in post2 is very complicated... I'm having trouble simply understanding it. I think I'll have to rest a little...

    Ok, after... three hours? I got the random movement function working. The multi-threading function is quite interesting to be honest(considering all the shit that can pop up during development). Luckily, I haven't met any problem like race condition, deadlock, livelock, or starvation... However, I occasionally get "QThread: Destroyed while thread is still running" error. Since it's a run time error, I can't really trace its source... So far, the most reasonable explanation is that a _wanderingThread takes longer to execute than the cool down interval. While the prior thread is still executing, the latter thread seize its pointer "self._wanderingThread", causing it to be destoried by python. 
    I'll set the cool down interval longer, and shorten the execution time. We'll see how it goes.