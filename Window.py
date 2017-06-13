import sys, os, time
import datetime
import curses
import WindowUtils
import WindowList
import random

class ScreenWindow(object):
    def __init__(self, screen):
        self.s = screen
        self.fh = open('log', 'w')

    def draw_menu(self, menus):
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLUE)
        self.s.bkgd(' ', curses.color_pair(1))
        index = 0
        for menu in menus:
            self.s.addstr(index+1, 1, str(index)+'. '+menu)
            index += 1

    def refresh(self, title):
        self.s.refresh()
        self.fh.write('>>>'+title+'<<< refresh called\n')

class MyWindow(object):

    def __init__(self, screen, windowType, sWindow, log):
        self.s = screen
        self.sWindow = sWindow
        self.sheight, self.swidth = self.s.getmaxyx()
        self.contents = []
        self.pages = 1
        self.currpage = 1
        self.windowType = windowType
        self.currx = 0
        self.curry = 0
        self.top = 0
        self.left = 0
        self.contentLines = []
        random.seed()
        self.log = log
        self.log.write('Instantiated window\n')

    def __del__(self):
        pass

    '''
    Call string parameters vch and hch cannot be defaulted to curses.ACS_VLINE 
    and curses.ACS_HLINE, respectively, in the call string because initscr() 
    has not yet been called when the call string is compiled, before any code 
    has run. They can be referenced in the method body because that is executed
    during run time, after initscr() has been called.
    '''
    def create(self, ht, wid, top=None, left=None, bkgnd=' ', vch=None, \
            hch=None, title=''):
        self.height = ht
        self.width = wid
        if not top:
            if self.sheight - ht > 0:
                self.top = random.randrange(1, self.sheight-ht)
            else:
                self.top = 1
        else:
            self.top = top
        if not left:
            if self.swidth - wid > 0:
                self.left = random.randrange(1, self.swidth-wid)
            else:
                self.left = 1
        else:
            self.left = left
        self.pagelen = ht - 2
        self.bkgnd = bkgnd
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
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title))/2, self.title,
                        curses.A_STANDOUT)
        if self.windowType != 'popup' and self.windowType != 'message':
            self.win.addstr(0, self.width-10, 'Page %d/%d'%
                            (self.currpage, self.pages), curses.A_STANDOUT)
            self.win.addstr(0, 2, 'Pos: %d,%d'%(self.currx, self.curry),
                            curses.A_STANDOUT)
        if self.windowType == 'message':
            self.win.addstr(self.height-1, (self.width-2)/2, ' OK ',
                            curses.A_STANDOUT)
        self.win.move(self.curry, self.currx)
        self.win.refresh()
        self.log.write('drawBorder[main] window (title='+self.title+')\n')

    def draw_contents(self, lastpage=False):
        self.win.clear()
        myx = 1 # position in window coords
        myy = 1
        if lastpage:
            self.currpage = self.pages
        firstrow = (self.currpage-1)*(self.pagelen)
        lastrow = firstrow + self.pagelen
        for i in range(firstrow, lastrow):
            try:
                # we are officially past the end of the contents array
                if i >= len(self.contents): break

                if myy < self.height-1:
                    self.win.addstr(myy, myx, self.contents[i][:self.width-2])
                    myy += 1 # go to the next line
            except:
                quit('Exception in drawContents trying to add row i=', i, ' "'+
                     self.contents[i]+'" at (%d,%d) page=%d, firstrow=%d, lastr'
                     'ow=%d'%(myx, myy, self.currpage, firstrow, lastrow))

        self.log.write('drawContents window (title='+self.title+')\n')
        self.win.refresh()
        self.read_content_lines()
        self.draw_border()

    """
    Returns the overall 0-based current row of the cursor in the content array 
    based on the 0-based pageRow and current 1-based page number
    """
    def current_row(self, pageRow):
        return (self.currpage-1)*self.pagelen + pageRow


    # Every window comes here
    def delete(self):
        self.win.clear()
        self.win.refresh()
        self.log.write('delete window (title='+self.title+')\n')
        del self.win

        # pops this window off the window list, then forces a redraw of all
        # remaining windows
        WindowList.pop_window(self.log)


    def read_content_lines(self):
        # Read in window contents as list of strings from top to bottom
        # only read in the content lines, not the border
        for y in range(1, self.height):
            self.contentLines.append(self.win.instr(y, 1))
        self.log.write('readContentLines window (title='+self.title+')\n')

    def draw_content_lines(self):
        y = 1
        for line in self.contentLines:
            self.win.addstr(y, 1, line)
            y += 1
        self.win.refresh()
        self.drawBorder()
        self.log.write('drawContentLines window (title='+self.title+')\n')
'''
Subclass of MyWindow
'''
class PopupWindow(MyWindow):

    def __init__(self, screen, n, fgcolor, bgcolor, sWindow, log):
        self.n = n
        self.fgcolor = fgcolor
        self.bgcolor = bgcolor
        curses.init_pair(n, fgcolor, bgcolor)
        super(PopupWindow, self).__init__(screen, 'popup', sWindow, log)

    def draw_border(self):
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title))/2, self.title,
                        curses.A_STANDOUT)
        self.win.move(self.curry, self.currx)
        self.win.refresh()
        self.read_content_lines()

'''
Subclass of MyWindow
'''
class MessageWindow(MyWindow):

    def __init__(self, screen, n, fgcolor, bgcolor, sWindow, log):
        self.n = n
        self.fgcolor = fgcolor
        self.bgcolor = bgcolor
        curses.init_pair(n, fgcolor, bgcolor)
        super(MessageWindow, self).__init__(screen, 'message', sWindow, log)

    def draw_border(self):
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title))/2, self.title,
                        curses.A_STANDOUT)
        self.win.addstr(self.height-1, (self.width-2)/2, ' OK ',
                        curses.A_STANDOUT)
        self.win.move(self.curry, self.currx)
        self.win.refresh()
        self.read_content_lines()

