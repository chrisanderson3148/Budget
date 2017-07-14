import sys
import curses
import WindowList
import random


class ScreenWindow(object):
    """Screen window class"""

    # class variables
    screen = None
    log = None

    @classmethod
    def init_screen(cls):
        """Starts up curses and returns the screen object
        
        :rtype Any:
        """
        cls.screen = curses.initscr()
        cls.log = open('log', 'w')

        # Initialize color capability
        curses.start_color()

        # Draw main screen border
        # N.B.: ACS_* elements are added to curses only after initscr() is called.
        # That's why pylint and pycharm do not find them.
        cls.screen.box(curses.ACS_VLINE, curses.ACS_HLINE)

        # Add title to the border
        title = ' Budget Edit Program v2.0 '
        dummy, width = cls.screen.getmaxyx()
        cls.screen.addstr(0, (width - len(title)) / 2, title, curses.A_STANDOUT)
        cls.screen.refresh()

        # Set some globals
        curses.noecho()
        curses.cbreak()
        cls.screen.keypad(1)

        # return the screen
        return cls.screen

    @classmethod
    def my_quit(cls, message):
        """Properly clean up and close curses before sys.exit() otherwise it leaves the terminal in a bad
        state. Optionally leave a quit message on the terminal.
        
        :param str message: the message to optionally print to the console after curses is gracefully
        closed.
        """
        curses.nocbreak()
        cls.screen.keypad(0)
        curses.echo()
        curses.endwin()
        if message:
            print message
        cls.log.close()
        print "Closed log file"
        sys.exit(0)

    def draw_menu(self, menus):
        """Draw the menus on the screen
        
        :param list menus: a list of strings, one for each menu item
        """
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLUE)
        self.screen.bkgd(' ', curses.color_pair(1))
        index = 0
        for menu in menus:
            self.screen.addstr(index + 1, 1, str(index) + '. ' + menu)
            index += 1

    def refresh(self, title):
        """Redraw the screen
        
        :param str title: the title for the screen window
        """
        self.screen.refresh()
        self.log.write('>>>' + title + '<<< refresh called\n')


class MyWindow(ScreenWindow):
    """Modified Curses windows class used for displaying multiple windows at the same time
    
    :param Any screen: the curses screen object to initialize the screen object
    :param str window_type: internal window type (like 'edit', 'dialog', etc)
    """

    def __init__(self, window_type):
        self.s_height, self.s_width = self.screen.getmaxyx()
        self.contents = []
        self.pages = 1
        self.page_len = 0
        self.background_char = ' '
        self.vch = '|'
        self.hch = '-'
        self.current_page = 1
        self.window_type = window_type
        self.curr_x = 0
        self.curr_y = 0
        self.width = self.height = 0
        self.top = 0
        self.left = 0
        self.title = ''
        self.win = None
        self.content_lines = []
        random.seed()
        super(MyWindow, self).__init__()
        self.log.write('Instantiated window\n')

    def __del__(self):
        pass

    '''
    '''
    def create(self, ht, wid, top=None, left=None, background_char=' ', vch=None, hch=None, title=''):
        """Call string parameters vch and hch cannot be defaulted to curses.ACS_VLINE and
        curses.ACS_HLINE, respectively, in the call string because initscr() has not yet been called
        when the call string is compiled, before any code has run. They can be referenced in the method
        body because that is executed during run time, after initscr() has been called.
        
        :param int ht: height of the window
        :param int wid: width of the window
        :param int top: the top of the window in screen coordinates
        :param int left: the left of the window in screen coordinates
        :param char background_char: the background fill character of the window
        :param char vch: The character to draw the vertical boundaries of the window
        :param char hch: the character to draw the horizontal boundaries of the window
        :param str title: the title of the window, drawn centered on the top border
        """
        self.height = ht
        self.width = wid
        if not top:
            if self.s_height - ht > 0:
                self.top = random.randrange(1, self.s_height - ht)
            else:
                self.top = 1
        else:
            self.top = top
        if not left:
            if self.s_width - wid > 0:
                self.left = random.randrange(1, self.s_width - wid)
            else:
                self.left = 1
        else:
            self.left = left
        self.page_len = ht - 2
        self.background_char = background_char
        if not vch:
            self.vch = curses.ACS_VLINE
        else:
            self.vch = vch
        if not hch:
            self.hch = curses.ACS_HLINE
        else:
            self.hch = hch
        self.title = title
        self.win = curses.newwin(self.height, self.width, self.top, self.left)
        self.draw_border()
        self.log.write('Created window (title='+title+')\n')

    def draw_border(self):
        """Draw my border"""
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title))/2, self.title, curses.A_STANDOUT)
        if self.window_type != 'popup' and self.window_type != 'message':
            self.win.addstr(0, self.width - 10, 'Page %d/%d' % (self.current_page, self.pages),
                            curses.A_STANDOUT)
            self.win.addstr(0, 2, 'Pos: %d,%d' % (self.curr_x, self.curr_y), curses.A_STANDOUT)
        if self.window_type == 'message':
            self.win.addstr(self.height-1, (self.width-2)/2, ' OK ', curses.A_STANDOUT)
        self.win.move(self.curr_y, self.curr_x)
        self.win.refresh()
        self.log.write('drawBorder[main] window (title='+self.title+')\n')

    def draw_contents(self, last_page=False):
        """Draw my contents
        
        :param bool last_page: whether or not this is the last displayed page
        """
        self.win.clear()
        myx = 1  # position in window coordinates
        myy = 1
        if last_page:
            self.current_page = self.pages
        first_row = (self.current_page - 1) * self.page_len
        last_row = first_row + self.page_len
        for i in range(first_row, last_row):
            try:
                # we are officially past the end of the contents array
                if i >= len(self.contents):
                    break
                if myy < self.height-1:
                    self.win.addstr(myy, myx, self.contents[i][:self.width-2])
                    myy += 1  # go to the next line
            except Exception:
                error_message = 'Exception in drawContents trying to add row i={} "{}" at ({},{}) '
                'page={}, first_row={}, last_row={}'.format(i, self.contents[i], myx, myy,
                                                            self.current_page, first_row, last_row)
                self.my_quit(error_message)

        self.log.write('drawContents window (title='+self.title+')\n')
        self.win.refresh()
        self.read_content_lines()
        self.draw_border()

    """
    Returns the overall 0-based current row of the cursor in the content array 
    based on the 0-based pageRow and current 1-based page number
    """
    def current_row(self, page_row):
        return (self.current_page - 1) * self.page_len + page_row

    # Every window comes here
    def delete(self):
        self.win.clear()
        self.win.refresh()
        self.log.write('delete window (title='+self.title+')\n')
        del self.win

        # pops this window off the window list, then forces a redraw of all remaining windows
        WindowList.pop_window(self.log)

    def read_content_lines(self):
        # Read in window contents as list of strings from top to bottom only read in the content lines,
        # not the border
        for y in range(1, self.height):
            self.content_lines.append(self.win.instr(y, 1))
        self.log.write('readContentLines window (title='+self.title+')\n')

    def draw_content_lines(self):
        y = 1
        for line in self.content_lines:
            self.win.addstr(y, 1, line)
            y += 1
        self.win.refresh()
        self.drawBorder()
        self.log.write('drawContentLines window (title='+self.title+')\n')


class PopupWindow(MyWindow):

    def __init__(self, n, fgcolor, bgcolor):
        self.n = n
        self.fgcolor = fgcolor
        self.bgcolor = bgcolor
        curses.init_pair(n, fgcolor, bgcolor)
        super(PopupWindow, self).__init__('popup')

    def draw_border(self):
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title))/2, self.title, curses.A_STANDOUT)
        self.win.move(self.curr_y, self.curr_x)
        self.win.refresh()
        self.read_content_lines()


class MessageWindow(MyWindow):

    def __init__(self, n, fg_color, bg_color):
        self.n = n
        self.fg_color = fg_color
        self.bg_color = bg_color
        curses.init_pair(n, fg_color, bg_color)
        super(MessageWindow, self).__init__('message')

    def draw_border(self):
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title))/2, self.title, curses.A_STANDOUT)
        self.win.addstr(self.height-1, (self.width-2)/2, ' OK ', curses.A_STANDOUT)
        self.win.move(self.curr_y, self.curr_x)
        self.win.refresh()
        self.read_content_lines()

