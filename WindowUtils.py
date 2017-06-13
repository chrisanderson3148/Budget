import unicodedata
import curses
import WindowList
from Window import PopupWindow
from Window import MessageWindow

'''
Displays message for 1 second, then removes the popup
'''
def popup_message_auto(s, message, sw, log):
    _my_win = MessageWindow(
            s, 5, curses.COLOR_BLACK, curses.COLOR_YELLOW, sw, log)
    _my_win.create(5, len(message)+5, title=' Message ')
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(5))
    _my_win.win.addstr(2, 2, message)
    _my_win.win.refresh()

    time.sleep(1)

    _my_win.delete()

'''
Displays message until user hits <enter>
'''
def popup_message_ok_dialog(d, message, title=' Message '):
    d.msgbox(message, title=title)

def popup_message_ok(s, message, sw, log, title=' Message '):
    _my_win = MessageWindow(
            s, 5, curses.COLOR_BLACK, curses.COLOR_YELLOW, sw, log)

    # Sometimes we get unicode strings from our source. Just in case we do,
    # convert it to ASCII.
    if type(message) is unicode:
        message = message.encode('ascii', 'replace')

    if type(message) is str:
        _max_len = 80
        if len(message) > _max_len:
            _msg_chunks = [message[i:i+_max_len] \
                            for i in range(0, len(message), _max_len)]
            _my_ht = len(_msg_chunks) + 4

            _my_win.create(_my_ht, _max_len+5,
                           top=max(1, _my_win.sheight/3 - _my_ht/2),
                           left=max(1, (_my_win.swidth-(_max_len+5))/2),
                           title=title)
            WindowList.add_window(_my_win.win)
            _my_win.win.bkgd(' ', curses.color_pair(5))
            y = 2
            for chunk in _msg_chunks:
                _my_win.win.addstr(y, 2, chunk)
                y += 1
        else:
            _my_wid = max(len(message) + 5, len(title)+5)
            _my_win.create(5, _my_wid, top=max(1, (_my_win.sheight/3 - 2)),
                           left=max(1, (_my_win.swidth-_my_wid)/2), title=title)
            WindowList.add_window(_my_win.win)
            _my_win.win.bkgd(' ', curses.color_pair(5))
            _my_win.win.addstr(2, 2, message)
    elif type(message) is list:
        _max_len = 0
        for _msg in message:
            if len(_msg) > _max_len:
                _max_len = len(_msg)
        _wid = max(_max_len+5, len(title)+5)
        _my_win.create(4+len(message), _wid,
                       top=max(1, (_my_win.sheight/3 - (4+len(message))/2)),
                       left=max(1, (_my_win.swidth-_wid)/2), title=title)
        WindowList.add_window(_my_win.win)
        _my_win.win.bkgd(' ', curses.color_pair(5))
        y = 2
        for _msg in message:
            _my_win.win.addstr(y, 2, _msg)
            y += 1
    else:
        raise ValueError('popupMessageOk(): Did not recognize message type: '+
                         str(type(message)))

    _my_win.win.refresh()

    while True:
        i = s.getch()
        if i == ord('\n'):
            break

    _my_win.delete()

'''
Displays a short list of strings horizontally that the user can choose from,
tabbing to highlight and select.
e.g., choice = popupGetMultipleChoice('Choose one:', ['Yes', 'No', 'Elephant',
'Mouse', 'Green', 'Red'], 'Mouse')
'''
def popup_get_multiple_choice(s, wintitle, choices, default, sw, log):
    _my_win = PopupWindow(s, 5, curses.COLOR_BLACK, curses.COLOR_YELLOW, sw,
                          log)
    _len_choices = 0
    for ch in choices:
        _len_choices += len(ch)
    _len_choices += len(choices) - 1 # add one space between each choice
    if len(wintitle) > _len_choices:
        _win_wid = len(wintitle) + 5
    else:
        # add some buffer on each end of the list of choices
        _win_wid = _len_choices + 5

    _my_win.create(5, _win_wid,
                   top=max(1, (_my_win.sheight/3 - 2)),
                   left=max(1, (_my_win.swidth-_win_wid)/2),
                   title=wintitle)
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(5))
    _tabarr = list()
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
        elif _ch == default: # not necessarily the first in the list
            _my_win.win.addstr(2, _start, _ch, curses.A_REVERSE)
            _idx = i
            _prev_index = _idx
        else:
            _my_win.win.addstr(2, _start, _ch)
        _tabarr.append([_start, 2, _ch])
        _my_win.win.refresh()
        _start += len(_ch) + 1
        i += 1

    while True:
        i = s.getch()
        if i == ord('\t'):
            _idx = (_idx + 1) % len(_tabarr)
        elif i == ord('\n'):
            break

        # highlight new choice
        _my_win.win.addstr(_tabarr[_idx][1], _tabarr[_idx][0],
                           _tabarr[_idx][2], curses.A_REVERSE)

        # unhighlight old choice
        _my_win.win.addstr(_tabarr[_prev_index][1], _tabarr[_prev_index][0],
                           _tabarr[_prev_index][2])

        # Move cursor to new choice
        _my_win.win.move(_tabarr[_idx][1], _tabarr[_idx][0])
        _my_win.win.refresh()
        _prev_index = _idx

    _my_win.delete()
    return _tabarr[_idx][2]

'''
Displays a short list of strings vertically that the user can choose from,
tabbing to highlight and select.
e.g., choice = popupGetMultipleChoice('Choose one:', ['Yes', 'No', 'Elephant',
'Mouse', 'Green', 'Red'], 'Mouse')
'''
def popup_get_multiple_choice_vert(s, wintitle, choices, default, sw, log):
    _my_win = PopupWindow(s, 5, curses.COLOR_BLACK, curses.COLOR_YELLOW, sw,
                          log)

    _max_choice_width = 0
    for _choice in choices:
        if len(_choice) > _max_choice_width: _max_choice_width = len(_choice)

    _win_wid = max(len(wintitle), _max_choice_width) + 5
    _win_ht = len(choices) + 4

    _my_win.create(_win_ht, _win_wid,
                   top=max(1, (_my_win.sheight/3 - _win_ht/2)),
                   left=max(1, (_my_win.swidth-_win_wid)/2),
                   title=wintitle)
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
        i = s.getch()
        if i == ord('\t') or i == ord('j'):
            _idx = (_idx + 1) % len(_tab_arr)
        elif i == ord('k'):
            _idx -= 1
            if _idx < 0: _idx = len(_tab_arr)-1
        elif i == ord('\n'):
            break

        # highlight new choice
        _my_win.win.addstr(_tab_arr[_idx][1], _tab_arr[_idx][0],
                           _tab_arr[_idx][2], curses.A_REVERSE)

        # unhighlight old choice
        _my_win.win.addstr(_tab_arr[_prev_index][1],
                           _tab_arr[_prev_index][0],
                           _tab_arr[_prev_index][2])

        # Move cursor to new choice
        _my_win.win.move(_tab_arr[_idx][1], _tab_arr[_idx][0])
        _my_win.win.refresh()
        _prev_index = _idx

    _my_win.delete()
    return _tab_arr[_idx][2]

'''
Lets user choose between 'YES' and 'NO', tabbing to highlight and select each
choice.
e.g., choice = popupGetYesNo('Continue?')
'''
def popup_get_yes_no(s, wintitle, sw, log, default='YES'):
    return popup_get_multiple_choice(s, wintitle, ['YES', 'NO'], default, sw,
                                     log)

def popup_get_text_dialog(d, wintitle):
    _code, _text = d.inputbox(
            '', title=wintitle,
            width=(0 if len(wintitle) < 20 else len(wintitle)+4))
    return _code, _text

def popup_get_text(s, wintitle, sw, log):
    _my_win = PopupWindow(s, 6, curses.COLOR_MAGENTA, curses.COLOR_YELLOW, sw,
                          log)
    _my_wid = len(wintitle) + 5

    _my_win.create(5, _my_wid, top=max(1, _my_win.sheight/3 - 2),
                   left=max(1, (_my_win.swidth-_my_wid)/2),
                   title=wintitle)
    WindowList.add_window(_my_win.win)
    _my_win.win.bkgd(' ', curses.color_pair(6))
    _my_win.win.addstr(2, 3, '            ', curses.A_UNDERLINE)
    _my_win.win.move(2, 3)

    curses.echo()
    _text = _my_win.win.getstr(2, 3)
    curses.noecho()

    _my_win.delete()
    return _text

