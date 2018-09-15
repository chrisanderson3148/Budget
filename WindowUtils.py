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


def redraw_list(my_win, values, top_offset, y_top, max_displayed):
    my_win.win.erase()
    my_win.draw_border()
    for i in range(top_offset, top_offset+max_displayed):
        curr_y = y_top + i - top_offset
        value = values[i]
        my_win.win.addstr(curr_y, 1, value)
        my_win.win.refresh()  # redraw the window


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

    # Determine maximum number of choices displayed at a time
    if len(choices) + 4 > _my_win.s_height:
        max_displayed_choices = _my_win.s_height - 4
    else:
        max_displayed_choices = len(choices)

    _win_wid = max(len(win_title), _max_choice_width) + 5
    _win_ht = max_displayed_choices + 3

    _my_win.create(_win_ht, _win_wid, top=max(1, (_my_win.s_height / 3 - _win_ht / 2)),
                   left=max(1, (_my_win.s_width - _win_wid) / 2), title=win_title)
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(5))
    _tab_arr = list()
    prev_highlighted_choice = 0
    highlighted_choice = 0  # index of highlighted choices element

    # Draw the selections and highlight the default choice
    y_top = 2  # y-coordinate of list top in window
    list_offset = 0  # list element at top of display
    for i in range(list_offset, max_displayed_choices):
        choice = choices[i]
        if not default:  # no default set, highlight first element
            if i == list_offset:
                _my_win.win.addstr(i+y_top, 1, choice, curses.A_REVERSE)
                highlighted_choice = i
                prev_highlighted_choice = highlighted_choice
                current_y = i + y_top
            else:
                _my_win.win.addstr(i+y_top, 1, choice)
        elif choice == default:  # there is a default set, highlight that one
            _my_win.win.addstr(i+y_top, 1, choice, curses.A_REVERSE)
            highlighted_choice = i
            prev_highlighted_choice = highlighted_choice
            current_y = i + y_top
        else:  # don't highlight this element
            _my_win.win.addstr(i+y_top, 1, choice)

        # Record the choice and position in tab_arr
        _tab_arr.append([1, i+y_top, choice])
        _my_win.win.refresh()  # redraw the window

    # handle selection process
    previous_y = current_y
    while True:
        command = ScreenWindow.screen.getch()
        if command == ord('\t') or command == ord('j'):  # move selector down
            if highlighted_choice + 1 < len(choices):
                prev_highlighted_choice = highlighted_choice
                highlighted_choice += 1  # only increment if before last element
                previous_y = current_y
                current_y += 1
        elif command == ord('k'):  # move selector up
            if highlighted_choice > 0:
                prev_highlighted_choice = highlighted_choice
                highlighted_choice -= 1  # only decrement if after first element
                previous_y = current_y
                current_y -= 1
        elif command == ord('\n'):  # make selection
            break

        # calculate list_offset (top of list offset)
        if current_y < y_top:
            current_y = y_top
            list_offset -= 1
            redraw_list(_my_win, choices, list_offset, y_top, max_displayed_choices)
        elif current_y > y_top + max_displayed_choices - 1:
            current_y = y_top + max_displayed_choices - 1
            list_offset += 1
            redraw_list(_my_win, choices, list_offset, y_top, max_displayed_choices)

        # unhighlight old choice only if highlighted line is different
        if previous_y != current_y:
            _my_win.win.addstr(previous_y, 1, choices[prev_highlighted_choice])

        # highlight new choice
        _my_win.win.addstr(current_y, 1, choices[highlighted_choice], curses.A_REVERSE)

        # Move cursor to new choice
        _my_win.win.move(current_y, 1)
        _my_win.win.refresh()
        prev_highlighted_choice = highlighted_choice

    _my_win.delete()
    return choices[highlighted_choice]


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
