import sys
import Window

global screen, window_list
screen = None
window_list = list()

def initialize(s):
    screen = s
    window_list.append(screen)

def refresh_windows(log):
    log.write('WindowList.refreshWindows: window_list='+str(window_list)+'\n')
    for win in window_list:
        win.redrawwin()
        win.refresh()

def add_window(win):
    window_list.append(win)

def pop_window(log): # always removes the last window in the list (most recent)
    window_list.pop()
    refresh_windows(log)
