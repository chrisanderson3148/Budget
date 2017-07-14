"""Contains helper methods for the MyWindow class"""
import time
import curses
import WindowList
from Window import PopupWindow
from Window import MessageWindow
from Window import ScreenWindow


def popup_message_auto(message):
    """Display my message for 1 second, then automatically delete me.

    :param str message: the message to display in my content area
    """
    _my_win = MessageWindow(5, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    _my_win.create(5, len(message)+5, title=' Message ')
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(5))
    _my_win.win.addstr(2, 2, message)
    _my_win.win.refresh()

    time.sleep(1)

    _my_win.delete()


def popup_message_ok(message, title=' Message '):
    """Displays my message until the user hits <enter>

    Also accepts different types of 'message':
    1. A string with unicode - unicode is replaced with ASCII
    2. A string greater than 80 characters is divided into 80 character chunks and displayed one chunk
       per line.
    3. A list of strings - each string in the list is displayed one per line. The width of the window
       is adjusted to accommodate the longest string.

    :param str|list message: the message to display
    :param str title: the title of the window (default is ' Message ')
    """
    _my_win = MessageWindow(5, curses.COLOR_BLACK, curses.COLOR_YELLOW)

    # Sometimes we get unicode strings from our source. Just in case we do, convert it to ASCII.
    if isinstance(message, unicode):
        message = message.encode('ascii', 'replace')

    if isinstance(message, str):
        _max_len = 80
        if len(message) > _max_len:
            _msg_chunks = [message[i:i+_max_len] for i in range(0, len(message), _max_len)]
            _my_ht = len(_msg_chunks) + 4

            _my_win.create(_my_ht, _max_len + 5, top=max(1, _my_win.s_height / 3 - _my_ht / 2),
                           left=max(1, (_my_win.s_width - (_max_len + 5)) / 2), title=title)
            WindowList.add_window(_my_win.win)
            _my_win.win.bkgd(' ', curses.color_pair(5))
            pos_y = 2
            for chunk in _msg_chunks:
                _my_win.win.addstr(pos_y, 2, chunk)
                pos_y += 1
        else:
            _my_wid = max(len(message) + 5, len(title)+5)
            _my_win.create(5, _my_wid, top=max(1, (_my_win.s_height / 3 - 2)),
                           left=max(1, (_my_win.s_width - _my_wid) / 2), title=title)
            WindowList.add_window(_my_win.win)
            _my_win.win.bkgd(' ', curses.color_pair(5))
            _my_win.win.addstr(2, 2, message)
    elif isinstance(message, list):
        _max_len = 0
        for _msg in message:
            if len(_msg) > _max_len:
                _max_len = len(_msg)
        _wid = max(_max_len+5, len(title)+5)
        _my_win.create(4 + len(message), _wid,
                       top=max(1, (_my_win.s_height / 3 - (4 + len(message)) / 2)),
                       left=max(1, (_my_win.s_width - _wid) / 2), title=title)
        WindowList.add_window(_my_win.win)
        _my_win.win.bkgd(' ', curses.color_pair(5))
        pos_y = 2
        for _msg in message:
            _my_win.win.addstr(pos_y, 2, _msg)
            pos_y += 1
    else:
        raise ValueError('popupMessageOk(): Did not recognize message type: '+str(type(message)))

    _my_win.win.refresh()

    while True:
        i = ScreenWindow.screen.getch()
        if i == ord('\n'):
            break

    _my_win.delete()


def popup_get_multiple_choice(win_title, choices, default):
    """Displays a short list of strings horizontally that the user can choose from

    The user tabs to highlight and <enter> to select. For example,
    choice = popup_get_multiple_choice('Choose one:', ['Yes', 'No', 'Elephant', 'Mouse', 'Green', 'Red'],
                                       'Mouse')
    Returns the string of the choice the user selected.

    :param str win_title: the title of the window - helpful if it instructs the user
    :param list choices: a list of strings, one per choice
    :param str default: the default choice which is the one that is highlighted first
    :rtype: str
    """
    _my_win = PopupWindow(5, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    _len_choices = 0
    for choice in choices:
        _len_choices += len(choice)
    _len_choices += len(choices) - 1 # add one space between each choice
    if len(win_title) > _len_choices:
        _win_wid = len(win_title) + 5
    else:
        # add some buffer on each end of the list of choices
        _win_wid = _len_choices + 5

    _my_win.create(5, _win_wid, top=max(1, (_my_win.s_height / 3 - 2)),
                   left=max(1, (_my_win.s_width - _win_wid) / 2), title=win_title)
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(5))
    _tab_arr = list()
    _start = 3
    _prev_index = 0
    _idx = 0
    i = 0
    for _ch in choices:
        if not default:
            if i == 0:
                _my_win.win.addstr(2, _start, _ch, curses.A_REVERSE)
                _idx = i
                _prev_index = _idx
            else:
                _my_win.win.addstr(2, _start, _ch)
        elif _ch == default:  # not necessarily the first in the list
            _my_win.win.addstr(2, _start, _ch, curses.A_REVERSE)
            _idx = i
            _prev_index = _idx
        else:
            _my_win.win.addstr(2, _start, _ch)
        _tab_arr.append([_start, 2, _ch])
        _my_win.win.refresh()
        _start += len(_ch) + 1
        i += 1

    while True:
        i = ScreenWindow.screen.getch()
        if i == ord('\t'):
            _idx = (_idx + 1) % len(_tab_arr)
        elif i == ord('\n'):
            break

        # highlight new choice
        _my_win.win.addstr(_tab_arr[_idx][1], _tab_arr[_idx][0], _tab_arr[_idx][2], curses.A_REVERSE)

        # unhighlight old choice
        _my_win.win.addstr(_tab_arr[_prev_index][1], _tab_arr[_prev_index][0], _tab_arr[_prev_index][2])

        # Move cursor to new choice
        _my_win.win.move(_tab_arr[_idx][1], _tab_arr[_idx][0])
        _my_win.win.refresh()
        _prev_index = _idx

    _my_win.delete()
    return _tab_arr[_idx][2]


def popup_get_multiple_choice_vert(win_title, choices, default):
    """Displays a short list of strings vertically that the user can choose from

    The user tabs to highlight and <enter> to select. For example,
    choice = popup_get_multiple_choice('Choose one:', ['Yes', 'No', 'Elephant', 'Mouse', 'Green', 'Red'],
                                       'Mouse')
    Returns the string of the choice the user selected.

    :param str win_title: the title of the window - helpful if it instructs the user
    :param list choices: a list of strings, one per choice
    :param str default: the default choice which is the one that is highlighted first
    :rtype: str
    """
    _my_win = PopupWindow(5, curses.COLOR_BLACK, curses.COLOR_YELLOW)

    _max_choice_width = 0
    for _choice in choices:
        if len(_choice) > _max_choice_width:
            _max_choice_width = len(_choice)

    _win_wid = max(len(win_title), _max_choice_width) + 5
    _win_ht = len(choices) + 4

    _my_win.create(_win_ht, _win_wid, top=max(1, (_my_win.s_height / 3 - _win_ht / 2)),
                   left=max(1, (_my_win.s_width - _win_wid) / 2), title=win_title)
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(5))
    _tab_arr = list()
    _prev_index = 0
    _idx = 0
    i = 0

    # Draw the selections and highlight the default choice
    _start = 2
    for _ch in choices:
        if not default:
            if i == 0:
                _my_win.win.addstr(_start, 1, _ch, curses.A_REVERSE)
                _idx = i
                _prev_index = _idx
            else:
                _my_win.win.addstr(_start, 1, _ch)
        elif _ch == default:
            _my_win.win.addstr(_start, 1, _ch, curses.A_REVERSE)
            _idx = i
            _prev_index = _idx
        else:
            _my_win.win.addstr(_start, 1, _ch)
        _tab_arr.append([1, _start, _ch])
        _my_win.win.refresh()
        _start += 1
        i += 1

    while True:
        i = ScreenWindow.screen.getch()
        if i == ord('\t') or i == ord('j'):
            _idx = (_idx + 1) % len(_tab_arr)
        elif i == ord('k'):
            _idx -= 1
            if _idx < 0:
                _idx = len(_tab_arr)-1
        elif i == ord('\n'):
            break

        # highlight new choice
        _my_win.win.addstr(_tab_arr[_idx][1], _tab_arr[_idx][0], _tab_arr[_idx][2], curses.A_REVERSE)

        # unhighlight old choice
        _my_win.win.addstr(_tab_arr[_prev_index][1], _tab_arr[_prev_index][0], _tab_arr[_prev_index][2])

        # Move cursor to new choice
        _my_win.win.move(_tab_arr[_idx][1], _tab_arr[_idx][0])
        _my_win.win.refresh()
        _prev_index = _idx

    _my_win.delete()
    return _tab_arr[_idx][2]


def popup_get_yes_no(win_title, default='YES'):
    """Lets user choose between 'YES' and 'NO', tabbing to highlight and select each choice.

    For example, choice = popup_get_yes_no('Continue?')
    The default default choice is 'YES'.
    Returns the string of the choice the user selected.

    :param str win_title: the title of the window - helpful if it asks the user the yes/no question
    :param str default: the default choice which is the one that is highlighted first
    :rtype: str
    """
    return popup_get_multiple_choice(win_title, ['YES', 'NO'], default)


def popup_get_text(win_title):
    """Return text entered by the user

    :param str win_title: an instructive message describing what is wanted
    :rtype: str
    """
    _my_win = PopupWindow(6, curses.COLOR_MAGENTA, curses.COLOR_YELLOW)
    _my_wid = len(win_title) + 5

    _my_win.create(5, _my_wid, top=max(1, _my_win.s_height / 3 - 2),
                   left=max(1, (_my_win.s_width - _my_wid) / 2), title=win_title)
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(6))
    _my_win.win.addstr(2, 3, '            ', curses.A_UNDERLINE)
    _my_win.win.move(2, 3)

    curses.echo()
    _text = _my_win.win.getstr(2, 3)
    curses.noecho()

    _my_win.delete()
    return _text
