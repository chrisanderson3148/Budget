"""Class manages the window_list"""
from Window import ScreenWindow

# pylint: disable-msg=C0103
window_list = list()


def initialize():
    """Initialize the window_list"""
    global window_list

    window_list.append(ScreenWindow.screen)


def refresh_windows(instant):
    """Redraw each window in the window_list and log a message"""
    instant.my_log(f"window_list={str(window_list)}")
    for win in window_list:
        win.redrawwin()
        win.refresh()


def add_window(win):
    """Add a window to the window_list

    :param _curses.curses win: the curses window object to add to the window_list
    """
    window_list.append(win)


def pop_window(instant):  # always removes the last window in the list (most recent)
    """Remove the latest window object from the window_list"""
    window_list.pop()
    refresh_windows(instant)
