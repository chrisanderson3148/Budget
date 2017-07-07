#!/usr/bin/python

import MySQLdb
import sys, os, time, math
import datetime
import curses
import signal
import traceback
import WindowUtils
import WindowList

from budgetQueries import budgetDB
from editWindow import EditWindow
from Window import ScreenWindow
from operator import itemgetter
from mysettings import g

def init_screen():
    s = curses.initscr()

    # Initialize color capability
    curses.start_color()

    # Draw main screen border
    s.box(curses.ACS_VLINE, curses.ACS_HLINE)

    # Add title to the border
    title = ' Budget Edit Program v2.0 '
    height, width = s.getmaxyx()
    s.addstr(0, (width-len(title))/2, title, curses.A_STANDOUT)
    s.refresh()

    # Set some globals
    curses.noecho()
    curses.cbreak()
    s.keypad(1)

    # return the screen
    return s

def quit(message):
    curses.nocbreak()
    s.keypad(0)
    curses.echo()
    curses.endwin()
    if message: print message
    log.close()
    sys.exit(0)

def signal_handler(signal, frame):
    quit('Exit forced -- nothing saved')

'''
Called for new check transactions only
'''
def new_transaction():
    newtransaction = []
                                    # checks
    newtransaction.append(None)     # tdate
    newtransaction.append('')       # tnum
    newtransaction.append('')       # tpayee
    newtransaction.append('')       # tchecknum
    newtransaction.append('b')      # ttype
    newtransaction.append(0.0)      # tamt

    bud = list()
    bud.append(['UNKNOWN', 0.0, None])
    newtransaction.append(bud)      # budarray

    newtransaction.append('')       # comments
    newtransaction.append(None)     # clear_date

    return newtransaction

"""
Add a check to the database
"""
def do_add_check(entry=None):
    win = EditWindow(s, budDB, 3, curses.COLOR_BLUE, curses.COLOR_YELLOW, sw,
                     log)
    win.create(20, 80, title='Add Check')
    WindowList.add_window(win.win)
    win.win.bkgd(' ', curses.color_pair(3))

    if entry is None:
        entry = new_transaction()
        new = True
    else:
        new = False

    WindowUtils.popup_message_ok(s, str(entry), sw, log)

    win.draw_win(False,               # isMain
                 entry[g.tDate],      # transaction date
                 entry[g.tPayee],     # transaction payee
                 str(entry[g.tCkn]),  # transaction check number
                 entry[g.tAmount],    # transaction amount
                 entry[g.tBudarr],    # transaction budget list of lists
                 entry[g.tComment],   # transaction comment, if any
                 entry[g.tClearDate]) # check clear date

    changes = win.check_event_loop(entry, new)

    win.delete()
    return changes

"""
The entry is either a check entry or a main table entry
It now handles multi-budget transactions
OLD FORMAT
"""
def do_edit_win(entry):
    isCheck = entry[g.tCkn] > 0
    isMain = not isCheck

    # Where did this entry come from?
    if isCheck and len(entry) > g.tClearDate:
        # this is a check from the 'checks' table (which has a cleardate field)
        fromChecks = True
    else:
        # this is an entry from the 'main' table (check or not: has no
        # cleardate field)
        fromChecks = False

    read_only = isCheck and not fromChecks

    win = EditWindow(s, budDB, 4, curses.COLOR_BLACK, curses.COLOR_CYAN, sw,
                     log)

    if read_only:
        mytitle = 'VIEW ONLY - check from main table'
    else:
        mytitle = 'Edit '+('check' if isCheck else 'main')+' transaction budget'

    win.create(40, 80, title=mytitle)
    WindowList.add_window(win.win)
    win.win.bkgd(' ', curses.color_pair(4))
    if isMain:
        win.draw_win(True,              # isMain
                     entry[g.tDate],    # transaction date
                     entry[g.tPayee],   # transaction payee
                     entry[g.tType],    # transaction type
                     entry[g.tAmount],  # transaction amount
                     entry[g.tBudarr],  # transaction budget list of lists
                     entry[g.tComment], # transaction comment, if any
                     '')                # extra field (for main only)

    # Sometimes this function is called with entry coming from a 'main' table
    # query but of a check. That entry won't have a cleardate field because
    # it's from the 'main' table. Replace that field with 'xxx'.
    else:
        win.draw_win(False,               # isMain
                     entry[g.tDate],      # transaction date
                     entry[g.tPayee],     # transaction payee
                     str(entry[g.tCkn]),  # transaction check number
                     entry[g.tAmount],    # transaction amount
                     entry[g.tBudarr],    # transaction budget list of lists
                     entry[g.tComment],   # transaction comment, if any
                     (entry[g.tClearDate] if fromChecks else None)) # check cleared date (check only)

    changes = win.main_event_loop(isMain, entry, readonly=read_only)

    win.delete()
    return changes

'''
NEW FORMAT
'''
def do_edit_win_both(entry):
    isCheck = entry[g.tCkn] > 0
    isMain = not isCheck

    win = EditWindow(s, budDB, 4, curses.COLOR_BLACK, curses.COLOR_CYAN, sw,
                     log)
    win.create(40, 80, title='Edit '+('check' if isCheck else 'main')
               +' transaction budget')
    WindowList.add_window(win.win)
    win.win.bkgd(' ', curses.color_pair(4))
    if isMain:
        win.draw_win(True,               # isMain True => isCheck False
                     entry[g.tDate],     # transaction date
                     entry[g.tPayee],    # transaction payee
                     entry[g.tType],     # transaction type
                     entry[g.tAmount],   # transaction amount
                     entry[g.tBudarr],   # transaction budget list of lists
                     entry[g.tComment],  # transaction comment (if any)
                     '')                 # unused
    else:
        win.draw_win(False,                # isMain False => isCheck True
                     entry[g.tDate],       # transaction date
                     entry[g.tPayee],      # transaction payee
                     str(entry[g.tCkn]),   # transaction check number
                     entry[g.tAmount],     # transaction amount
                     entry[g.tBudarr],     # transaction budget list of lists
                     entry[g.tComment],    # transaction comment (if any)
                     entry[g.tClearDate])  # check clear date

    changes = win.main_event_loop(isMain, entry)

    win.delete()
    return changes

def get_search_parameters():
    table = WindowUtils.popup_get_multiple_choice(
        s, 'Select one of the tables:', ['main', 'checks'], '', sw, log)

    if table == 'main':
        columns = budDB.maincolumns
    elif table == 'checks':
        columns = budDB.checkscolumns

    field = WindowUtils.popup_get_multiple_choice_vert(
        s, 'Select one of the columns from table '+ table+':', columns, '',
        sw, log)
    if not field.upper() in columns:
        WindowUtils.popup_message_ok(
            s,
            'No such field "'+field+'" in table '+table+': {}'.format(columns),
            sw, log)
        return '', '', '', ''

    compare = WindowUtils.popup_get_multiple_choice(
        s, 'Select comparison:', ['equals', 'like'], '', sw, log).strip()
    if compare.lower() == 'equals':
        compare = '='

    if field.lower() == 'bud_category' and compare == '=':
        value = WindowUtils.popup_get_multiple_choice_vert(
            s, 'Select a budget category:', budDB.budcatlist, '', sw, log)
    else:
        value = WindowUtils.popup_get_text(
            s, 'Enter the value to search for:', sw, log)

    return table, field, compare, value

def do_transaction_list_window(dataArray, contentArray, myTitle, addEdit, lastPage, qFunc, *args):
    numrows = len(contentArray)
    listwin = EditWindow(s, budDB, 2, curses.COLOR_BLACK, curses.COLOR_GREEN, sw, log)

    winrows = min(numrows, listwin.sheight-5)
    listwin.create(winrows+2, 120, title=myTitle)
    WindowList.add_window(listwin.win)
    listwin.win.bkgd(' ', curses.color_pair(2))
    listwin.contents = contentArray
    listwin.pages = int(math.ceil(len(contentArray)/float(listwin.height-2)))
    listwin.draw_contents(lastpage=lastPage) # readContentLines is called in draw_contents()

    # check number is 0 for main transactions
    # display the list of transactions
    while True:
        # handle navigation and selection of window list - returns row number
        # of selection
        entryindex, command = getListItem(1, 1, winrows, listwin.win, mywin=listwin)
        if command == 'quit':
            listwin.delete()
            return

        if addEdit:
            resp = do_add_check(entry=dataArray[entryindex])
        elif len(args) == 4: # main and check transactions are combined edit the selected list item,
            # either check or main -- This may change the contents of this window
            resp = do_edit_win_both(dataArray[entryindex])
        else:
            # edit the selected list item -- This may change the contents of this window
            resp = do_edit_win(dataArray[entryindex])

        # There were changes made so re-query the database and update the listwin contents and data
        # arrays
        if resp:
            dataArray, contentArray, total = qFunc(*args)

            if contentArray is None or len(contentArray) == 0:
                listwin.delete()
                return

            listwin.contents = contentArray
            listwin.pages = int(math.ceil(len(contentArray)/float(listwin.height-2)))
        else:
            # redraw the list window contents after edit window is deleted
            listwin.draw_contents()
            WindowUtils.popup_message_ok(s, 'No changes made in edit window', sw, log)

        # redraw the list window contents after edit window is deleted
        listwin.draw_contents()


def do_budcat_query(budcat, theyear):
    if not budcat: budcat = 'UNKNOWN'
    budcat = budcat.upper()
    if budcat == 'ALL':
        if theyear == 'all':
            return ("select * from main where tran_checknum = '0' and tran_desc not like 'CHECK %' order"
                    "by bud_date;",
                    "select sum(bud_amount) from main where tran_checknum = '0' and tran_desc not like"
                    "'CHECK %' order by bud_date;")
        else:
            return ("select * from main where bud_date between '"+theyear+"-01-01' and '"+theyear
                    +"-12-31' and tran_checknum = '0' and tran_desc not like 'CHECK %' "
                    "order by bud_date;",
                    "select sum(bud_amount) from main where bud_date between '"+theyear+"-01-01' and '"
                    +theyear+"-12-31' and tran_checknum = '0' and tran_desc not like 'CHECK %' "
                    "order by bud_date;"
                   )
    else:
        if theyear == 'all':
            return ("select * from main where bud_category = '"+budcat+"' and tran_checknum = '0' and"
                    " tran_desc not like 'CHECK %' order by bud_date;",
                    "select sum(bud_amount) from main where bud_category = '"+budcat+"' and "
                    "tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;")
        else:
            return ("select * from main where bud_category = '"+budcat+"' and bud_date between '"
                    +theyear+"-01-01' and '"+theyear+"-12-31' and tran_checknum = '0' and tran_desc "
                    "not like 'CHECK %' order by bud_date;",
                    "select sum(bud_amount) from main where bud_category = '"+budcat+"' and "
                    "bud_date between '"+theyear+"-01-01' and '"+theyear+"-12-31' and "
                    "tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;")

def do_check_budcat_query(budcat, theYear):
    if not budcat: budcat = 'UNKNOWN'
    budcat = budcat.upper()
    if budcat == 'ALL':
        if theYear == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks order by bud_date;")
        else:
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks where bud_date between '"+theYear+"-01-01' and '"
                    +theYear+"-12-31' order by bud_date;")
    else:
        if theYear == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks where bud_cat = '"+budcat+"' order by bud_date;")
        else:
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks where bud_cat = '"+budcat+"' and bud_date between '"
                    +theYear+"-01-01' and '"+theYear+"-12-31' order by bud_date;")

'''
Same as do_check_budcat_query() above, but order the fields as do_budcat_query() for main
NEW FORMAT
'''
def do_check_budcat_query_asmain(budcat, theYear):
    if not budcat: budcat = 'UNKNOWN'
    budcat = budcat.upper()
    if budcat == 'ALL':
        if theYear == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks order by bud_date;",
                    "select sum(bud_amt) from checks;")
        else:
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks where bud_date between '"+theYear+"-01-01' and '"
                    +theYear+"-12-31' order by bud_date;",
                    "select sum(bud_amt) from checks where bud_date between '"+theYear+"-01-01' and '"
                    +theYear+"-12-31';")
    else:
        if theYear == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks where bud_cat = '"+budcat+"' order by bud_date;",
                    "select sum(bud_amt) from checks where bud_cat = '"+budcat+"';")
        else:
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks where bud_cat = '"+budcat+"' and bud_date between '"+theYear
                    +"-01-01' and '"+theYear+"-12-31' order by bud_date;",
                    "select sum(bud_amt) from checks where bud_cat = '"+budcat+"' and "
                    "bud_date between '"+theYear+"-01-01' and '"+theYear+"-12-31' order by bud_date;")

def do_month_query(yearmonth):
    return ("select * from main where bud_date between '"+yearmonth+"-01' and '"+yearmonth+"-31' and "
            "tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;",
            "select sum(bud_amount) from main where bud_date between '"+yearmonth+"-01' and '"
            +yearmonth+"-31' and tran_checknum = '0' and tran_desc not like 'CHECK %' "
            "order by bud_date;")

def do_check_month_query(yearmonth):
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            "checks where bud_date between '"+yearmonth+"-01' and '"+yearmonth+"-31' order by bud_date;")

def do_check_month_query_asmain(yearmonth):
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            "checks where bud_date between '"+yearmonth+"-01' and '"+yearmonth+"-31' order by bud_date;",
            "select sum(bud_amt) from checks where bud_date between '"+yearmonth+"-01' and '"
            +yearmonth+"-31';")

def do_uncleared_checks_query():
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            "checks where clear_date is null and tdate > '2005-12-31' and tamt != 0 "
            "order by tdate,tchecknum;")

def do_check_all_query():
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            "checks where tnum < 5000 order by tnum;")

'''
Create a query string based on 'field =/like value', where value is matched case-sensitive or not
TODO: This function has to be reworked so it can create a query for either main or checks
'''
def get_search_query(table, field, isorlike, value, casesensitive=True):
    if table == 'main':
        return ("select * from main where "+("BINARY " if casesensitive else "")+field+" "+isorlike+" '"
                +value+"' order by bud_date;", "select sum(bud_amount) from main where "+
                ("BINARY " if casesensitive else "")+field+" "+isorlike+" '"+value+"' "
                "order by bud_date;")
    else:
        return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments "
                "from checks where "+("BINARY " if casesensitive else "")+field+" "+isorlike+" '"
                +value+"' order by bud_date;",
                "select sum(bud_amt) from checks where "+("BINARY " if casesensitive else "")+field+" "
                +isorlike+" '"+value+"' order by bud_date;")

'''
Returns elemarray, contentarray, total
elemarray is a list of transactions retrieved directly from the database 
listquery
Each transaction is tran_date, tran_ID, tran_desc, tran_checknum, tran_type, tran_amount, [array of 3-element budget lists], comment
                        0          1        2            3            4            5                      6                     7

contentarray is a list of formatted strings of each row retrieved from the database listquery (corresponds 1-to-1 with elemarray)
total is the total of the individual transaction amounts for the listquery

listquery returns 10 fields:
    tran_date, tran_ID, tran_desc, tran_checknum, tran_type, tran_amount, bud_category, bud_amount, bud_date, comment
        0         1         2             3           4           5            6             7         8         9

Multi-budget transactions
If tran_ID ends with '-\\d+', then the transaction is part of a multi-budget uber-transaction
'''
def get_data_array_and_content_array(listquery, totalquery):
    # Do the list query
    cur = budDB.executeQuery(listquery)

    numrows = cur.rowcount
    if numrows == 0:
        return None, None, None

    # Fill out the elemarray and contentarray
    elemarray = []
    contentarray = []
    for row in cur:
        bud_array = list()
        thebud = list()
        try:
            t = row[g.tID].split('-') # Check transaction ID for multibudget tag
        except:
            (etype, value, tb) = sys.exc_info()
            WindowUtils.popup_message_ok(s, ['transaction ID type ('+str(type(row[g.tID]))+'): '
                                         +value.message, listquery], sw, log)
            return

        # Handle multibudget items
        if len(t) > 1 and t[-1].isdigit():

            # Create transaction ID without multibudget part
            idx = row[g.tID].rfind('-')
            tran_ID_pre = row[g.tID][:idx]

            # Do second query to grab all records matching the shortened
            # transaction ID
            cur2 = budDB.executeQuery2('select bud_category, bud_amount, bud_date from main where '
                                       'tran_ID like "'+tran_ID_pre+'-%" order by bud_date;')

            # Add all budget results to bud_array
            for brow in cur2:
                bud_array.append([brow[0], brow[1], brow[2]])
            thebud = [row[6], row[7], row[8]]

        # Handle single budget items
        else: # Put only one row in bud_array
            # The query returns 3 extra fields for each budget transaction.
            # These are combined into the bud_array.
            bud_array.append([row[6], row[7], row[8]])
            thebud = [row[6], row[7], row[8]]


        # Create the entry in elemarray
        elem = [row[g.tDate],     # transaction date
                row[g.tID],       # transaction ID
                row[g.tPayee],    # transaction payee
                row[g.tCkn],      # transaction check number
                row[g.tType],     # transaction type
                row[g.tAmount],   # transaction amount
                bud_array,        # transaction budget list of lists
                row[g.tCommentQ]] # transaction comment, if any
        elemarray.append(elem)

        # Create the entry in contentarray. Multibudget entries are displayed
        # differently
        if len(bud_array) > 1: # multi-budget
            contentrow = '%-12s %4d %-40s %s %10.2f %-15s %s' % (
                (row[g.tDate].strftime('%m/%d/%Y') if row[g.tDate] else '---'), # transaction date
                row[g.tCkn],                            # transaction check number
                row[g.tPayee][:40],                     # transaction description
                (row[g.tType] if 'str' in str(type(row[g.tType])) else 'b'), # transaction type
                row[g.tAmount],                         # transaction amount
                'MULTI',                                # budget category
                row[g.tCommentQ])                       # transaction comment
        else: # single budget
            contentrow = '%-12s %4d %-40s %s %10.2f %-15s %s' % (
                (thebud[2].strftime('%m/%d/%Y') if thebud[2] else '---'), # bud_date
                row[g.tCkn],                          # transaction check number
                row[g.tPayee][:40],                   # transaction description
                (row[g.tType] if 'str' in str(type(row[g.tType])) else 'b'), # transaction type
                thebud[1],                            # bud_amount
                thebud[0],                            # bud_category
                row[g.tCommentQ])                     # transaction comment
        contentarray.append(contentrow)

    # Get the total of all entries using the totalquery
    #WindowUtils.popup_message_ok(s, totalquery, sw, log)
    total = 0.0
    cur = budDB.executeQuery(totalquery)
    for row in cur:
        total = row[0]

    # Return the results
    return elemarray, contentarray, total

'''
This function combines getting data arrays for both main and checks tables, and combines them together
in one data array and content array, displayed mixed together. To do this more easily, the format of the
checks query has changed so the fields between the two arrays match.
NEW FORMAT
'''
def get_data_array_and_content_array_both(mainlistquery, maintotalquery, checkslistquery,
                                          checkstotalquery):
    # Do the main list query
    cur = budDB.executeQuery(mainlistquery)

    nummainrows = cur.rowcount

    # Fill out the mainelemarray
    mainelemarray = []
    for row in cur:
        bud = list() # list of lists - contains all budget arrays for the given transaction
        # (multibudget can have more than one)
        thebud = list() # list - contains the ONE budget array to be displayed
        t = row[g.tID].split('-') # Check transaction ID for multibudget tag

        # Handle multibudget items
        if len(t) > 1 and t[-1].isdigit():
            # Create transaction ID without multibudget part
            idx = row[g.tID].rfind('-')
            tran_ID_pre = row[g.tID][:idx]

            # Do second query to grab all records matching the shortened transaction ID
            cur2 = budDB.executeQuery2('select bud_category, bud_amount, bud_date from main where '
                                       'tran_ID like "'+tran_ID_pre+'-%" order by bud_date;')

            # Add all budget results to bud
            for brow in cur2:
                bud.append([brow[0], brow[1], brow[2]])
            thebud = [row[6], row[7], row[8]]

        # Handle single budget items
        else: # Put only one row in bud
            bud.append([row[6], row[7], row[8]])
            thebud = [row[6], row[7], row[8]]

        # Create the entry in elemarray
        if not(g.tDate is None or bud[0][2] is None):
            elem = [row[g.tDate],     # transaction date
                    row[g.tID],       # transaction ID
                    row[g.tPayee],    # transaction description
                    row[g.tCkn],      # transaction check number
                    row[g.tType],     # transaction type
                    row[g.tAmount],   # transaction amount
                    bud,              # transaction budget list of lists
                    row[g.tCommentQ], # transaction comment (if any)
                    '',               # filler field so both checks and main
                                      # elemarrays have the same number of rows
                    thebud]           # the one budget array to display
            mainelemarray.append(elem)

    # Do the checks list query
    cur = budDB.executeQuery(checkslistquery)

    numchecksrows = cur.rowcount
    if nummainrows + numchecksrows == 0:
        return None, None, None

    # Fill out the checkselemarray
    checkselemarray = []
    for row in cur:
        bud = list()
        thebud = list()

        t = row[g.tID].split('-')
        # is multi-budget. Fill the array of budget items with multiple elements
        if len(t) > 1 and t[-1].isdigit():
            idx = row[g.tID].rfind('-')
            tnum_pre = row[g.tID][:idx]
            cur2 = budDB.executeQuery2('select bud_cat, bud_amt, bud_date from checks where tnum like "'
                                       +tnum_pre+'-%" order by bud_date;')
            for brow in cur2:
                bud.append([brow[0], brow[1], brow[2]])
            thebud = [row[6], row[7], row[8]]

        # is single-budget. Put only one row in the array of budget items
        else:
            bud.append([row[6], row[7], row[8]])
            thebud = [row[6], row[7], row[8]]

        if not(g.tDate is None or bud[0][2] is None):
            elem = [row[g.tDate],     # transaction date
                    row[g.tID],       # transaction ID
                    row[g.tPayee],    # transaction payee
                    row[g.tCkn],      # transaction check number
                    'b',              # row[tType] is the clear_date -
                                      # overwriting with static transaction type
                    row[g.tAmount],   # transaction amount
                    bud,              # transaction budget list of lists
                    row[g.tCommentQ], # transaction comment, if any
                    row[g.tType],     # check clear date
                    thebud]           # the one budget array to display
            checkselemarray.append(elem)

    # Combine arrays for both queries and sort on budget date (element 6,0,2)
    # TODO: need to sort by transaction date (x[0]) for multi-budget transactions
    # TODO: cannot sort null dates (all canceled checks) -- FIXED do not include transactions with
    #       null dates (transaction or budget) in elemarray

    # cool way to sort list of lists by element in sub-list
    elemarray = sorted(mainelemarray+checkselemarray, key=lambda x: x[9][2])

    contentarray = []
    for row in elemarray:
        thebud = row[9]
        # Create the entry in contentarray. Multibudget entries are displayed differently
        if len(row[g.tBudarr]) > 1: # multibudget
            contentrow = '%-12s %-40s %4s %s %10.2f %-15s %s' % (
                (thebud[2].strftime('%m/%d/%Y')
                    if not thebud[2] is None else '---'), # budget date
                row[g.tPayee][:40], # transaction description
                row[g.tCkn],        # transaction check number (if any)
                row[g.tType],       # transaction type
                thebud[1],          # budget amount
                thebud[0],          # budget category
                row[g.tComment])    # transaction comment
        else: # single-budget
            contentrow = '%-12s %-40s %4s %s %10.2f %-15s %s' % (
                (thebud[2].strftime('%m/%d/%Y')
                 if not thebud[2] is None else '---'), # budget date
                row[g.tPayee][:40], # transaction description
                row[g.tCkn],        # transaction check number (if any)
                row[g.tType],       # transaction type
                thebud[1],          # budget amount
                thebud[0],          # budget category
                row[g.tComment])    # transaction comment (if any)
        contentarray.append(contentrow)

    # Get the total of all entries using the totalquery
    total = 0.0
    cur = budDB.executeQuery(maintotalquery)
    for row in cur:
        if row[0]: total = float(row[0])
    cur = budDB.executeQuery(checkstotalquery)
    for row in cur:
        if row[0]: total += float(row[0])

    # Return the results
    return elemarray, contentarray, total


'''
Returns elemarray, contentarray, None
elemarray is a list of 10 element arrays retrieved directly from the database
    query
elemarray is a list of transactions retrieved directly from the database query
contentarray is a list of formatted strings of each row retrieved from the
    database listquery (corresponds 1-to-1 with elemarray)

query returns 10 fields (OLD FORMAT):
    tnum, tchecknum, tamt, tdate, tpayee, bud_cat, bud_amt, bud_date, comments, clear_date
      0       1        2     3       4       5        6         7        8           9
OLD FORMAT
'''
def get_check_data_array_and_content_array(query):
    cur = budDB.executeQuery(query)
    numrows = cur.rowcount
    if numrows == 0:
        return None, None, None

    elemarray = []
    contentarray = []
    for row in cur:
        bud_array = list()
        thebud = list()
        t = row[g.tID].split('-')

        # is multi-budget. Fill the array of budget items with multiple elements
        if len(t) > 1 and t[-1].isdigit():
            idx = row[g.tID].rfind('-')
            tnum_pre = row[g.tID][:idx]
            cur2 = budDB.executeQuery2('select bud_cat,bud_amt,bud_date from checks where tnum like "'
                                       +tnum_pre+'-%" order by bud_date;')
            for brow in cur2:
                bud_array.append([brow[0], brow[1], brow[2]])
            thebud = [row[6], row[7], row[8]]

        else: # is single-budget. Put only one row in the array of budget items
            bud_array.append([row[6], row[7], row[8]])
            thebud = [row[6], row[7], row[8]]

        elem = [row[g.tDate],      # transaction date
                row[g.tID],        # transaction ID
                row[g.tPayee],     # transaction payee
                row[g.tCkn],       # transaction check number
                'b',               # transaction type
                row[g.tAmount],    # transaction amount
                bud_array,         # transaction budget list of lists
                row[g.tCommentQ],  # transaction comment, if any from query
                row[g.tClearDateQ]] # check clear date from query
        elemarray.append(elem)

        # multi-budget tdate tckn tpayee tamt cleardate bud_cat comments
        if len(bud_array) > 1:
            contentrow = '%-12s %-6d %-40s %10.2f %-12s %-15s %s' % (
                (bud_array[0][2].strftime('%m/%d/%Y')
                 if bud_array[0][2] is not None else '---'),
                row[g.tCkn],
                row[g.tPayee][:40],
                (row[g.tAmount] if row[g.tAmount] else 0.0),
                (row[g.tClearDateQ].strftime('%m/%d/%Y')
                 if row[g.tClearDateQ] is not None else '---'),
                'MULTI',
                row[g.tCommentQ])

        # single budget tdate tckn tpayee budamt cleardate bud_cat comments
        else:
            contentrow = '%-12s %-6d %-40s %10.2f %-12s %-15s %s' % (
                (row[g.tDate].strftime('%m/%d/%Y')
                 if row[g.tDate] is not None else '---'),
                row[g.tCkn],
                row[g.tPayee][:40],
                (row[g.tAmount] if row[g.tAmount] else 0.0),
                (row[g.tClearDateQ].strftime('%m/%d/%Y')
                 if row[g.tClearDateQ] is not None else '---'),
                thebud[0],
                row[g.tCommentQ])
        contentarray.append(contentrow)

    return elemarray, contentarray, None

'''
Should only be called in combination with doCheck_asmain_BudcatQuery() as the fields order is different
NEW FORMAT
'''
def get_check_data_array_asmain(listquery, totalquery):
    cur = budDB.executeQuery(listquery)
    numrows = cur.rowcount
    if numrows == 0:
        return None, None, None

    elemarray = []
    for row in cur:
        bud_array = list()
        t = row[g.tID].split('-')

        # is multi-budget. Fill the array of budget items with multiple elements
        if len(t) > 1 and t[-1].isdigit():
            idx = row[g.tID].rfind('-')
            tnum_pre = row[g.tID][:idx]
            cur2 = budDB.executeQuery2('select bud_cat,bud_amt,bud_date from checks where tnum like "'
                                       +tnum_pre+'-%" order by bud_date;')
            for brow in cur2:
                bud_array.append([brow[0], brow[1], brow[2]])

        # is single-budget. Put only one row in the array of budget items
        else:
            bud_array.append([row[6], row[7], row[8]])

        elem = [row[g.tDate],     # transaction date
                row[g.tID],       # transaction ID
                row[g.tPayee],    # transaction payee
                row[g.tCkn],      # transaction check number
                'b',              # transaction type
                row[g.tAmount],   # transaction amount
                bud_array,        # transaction budget list of lists
                row[g.tCommentQ], # transaction comment, if any from query
                row[g.tClearDateQ]]  # check clear date from query
        elemarray.append(elem)

    # Get the total of all entries using the totalquery
    total = 0.0
    cur = budDB.executeQuery(totalquery)
    for row in cur:
        total = row[0]

    return elemarray, total

def handle_edit_budget_by_budcat_both(budcat, theYear='all'):
    listquery, totalquery = do_budcat_query(budcat, theYear)

    # query to return checks with fields in same order as main query
    checklistquery, checktotalquery = do_check_budcat_query_asmain(budcat, theYear)

    elemarray, contentarray, total = get_data_array_and_content_array_both(
        listquery, totalquery, checklistquery, checktotalquery)

    # elem array is empty
    if not elemarray:
        WindowUtils.popup_message_ok(s, 'Budget category "'+budcat+'" is not in the database for year "'
                                     +theYear+'"', sw, log)
        return

    do_transaction_list_window(elemarray, contentarray, 'Budcat='+budcat+',Year='+theYear
                               +(' Total='+str(total) if not total is None else ''),
                               False, False, get_data_array_and_content_array_both, listquery,
                               totalquery, checklistquery, checktotalquery)

def handle_edit_budget_by_month_both(yearmonth):
    try:
        testdate = datetime.datetime.strptime(yearmonth+'-01', '%Y-%m-%d')
    except:
        (etype, value, tb) = sys.exc_info()
        WindowUtils.popup_message_ok(s, 'User entered "'+yearmonth+'": '+value.message, sw, log)
        return

    listquery, totalquery = do_month_query(yearmonth)
    checklistquery, checktotalquery = do_check_month_query_asmain(yearmonth)
    elemarray, contentarray, total = get_data_array_and_content_array_both(
        listquery, totalquery, checklistquery, checktotalquery)

    if elemarray is None:
        WindowUtils.popup_message_ok(s, 'Month "'+yearmonth+'" is not in the database', sw, log)
        return

    do_transaction_list_window(elemarray, contentarray, 'Month='+yearmonth
                               +(' Total='+str(total) if not total is None else ''),
                               False, False, get_data_array_and_content_array_both, listquery,
                               totalquery, checklistquery, checktotalquery)

def handle_edit_check_by_budcat(budcat, theYear='all'):
    query = do_check_budcat_query(budcat, theYear)
    elemarray, contentarray, total = get_check_data_array_and_content_array(query)
    if elemarray is None:
        WindowUtils.popup_message_ok(s, 'Budget category "'+budcat+'" is not in the "checks" database '
                                     'for year '+year, sw, log)
        return
    do_transaction_list_window(elemarray, contentarray, 'Budcat='+budcat+', Year='+year
                               +(' Total='+str(total) if not total is None else ''),
                               False, False, get_check_data_array_and_content_array, query)

def handle_edit_check_by_month(yearmonth):
    try:
        testdate = datetime.datetime.strptime(yearmonth+'-01', '%Y-%m-%d')
    except:
        (etype, value, tb) = sys.exc_info()
        WindowUtils.popup_message_ok(s, 'User entered "'+yearmonth+'": '+value.message, sw, log)
        return

    query = do_check_month_query(yearmonth)
    elemarray, contentarray, total = get_check_data_array_and_content_array(query)
    if elemarray is None:
        WindowUtils.popup_message_ok(s, 'Month "'+yearmonth+'" is not in the "checks" database', sw, log)
        return
    do_transaction_list_window(elemarray, contentarray, 'Month='+yearmonth
                               +(' Total='+str(total) if not total is None else ''),
                               False, False, get_check_data_array_and_content_array, query)

# OLD FORMAT
def do_query_cleared_unrecorded_checks():
    # elemarray is the list of cleared,unrecorded checks from the main table
    elemarray = []

    # contentarray is the list of strings that are displayed in the window
    contentarray = []

    # tnum, tchecknum, tamt, tdate, tpayee, bud_cat, bud_amt, bud_date, comments, clear_date
    #  0       1        2      3       4       5        6        7         8          9
    cur = budDB.executeQuery('select tran_checknum,tran_date,tran_amount from main where '
                             'tran_checknum != "0" and tran_type = "b" order by tran_checknum;')
    mytotal = 0.0

    # for every cleared CU check, see if it also exists as a transaction in the checks database, with at
    # least an amount
    for row in cur:
        cur2 = budDB.executeQuery2('select tchecknum from checks where tchecknum = "'
                                   +str(row[0])+'" and tamt is not null;')
        if cur2.rowcount == 0: # The row is a cleared, unrecorded check
            checkentry = []
            budarray = list()
            checkentry.append(None)        # tdate is None because the check's transaction date is not
                                           # known at this time
            checkentry.append(str(row[0])) # tnum (varchar)
            checkentry.append('')          # tpayee (varchar), unknown
            checkentry.append(row[0])      # tchecknum (int)
            checkentry.append('b')         # ttype
            checkentry.append(row[2])      # tamt (decimal/float)
            budarray.append(['', row[2], None])
            checkentry.append(budarray)    # budarray
            checkentry.append('')          # comments (varchar), unknown
            checkentry.append(row[1])      # clear_date is the main table's transaction date,
                                           # the date it cleared the bank
            elemarray.append(checkentry)
            contentarray.append('%d %12s %7.2f' % (row[0], row[1].strftime('%m/%d/%Y'), row[2]))
            mytotal += float(row[2])

    return elemarray, contentarray, mytotal

def do_query_missing_unrecorded_checks():
    cnumdict = {}
    missingchecks = []
    cur = budDB.executeQuery('select tnum from checks where tnum < 5000 order by tnum;')
    first = True
    lastcheck = ''
    for row in cur:
        if first:
            # some checknumbers have hyphens (multi-budget). Only keep the checknumber part.
            firstcheck = row[0].split('-')[0]
            first = False
        cnumdict[row[0].split('-')[0]] = True
        lastcheck = row[0].split('-')[0]

    # Check #s 2869-2929 and 3882-3989 are missing because of ordering new checkbooks and skipping these
    # ranges. Just skip them as they clutter up the real missing checks.
    for i in (range(int(firstcheck), 2869) # adding ranges like this is not valid in Python 3
              +range(2930, 3882)
              +range(3990, int(lastcheck))):
        if not str(i) in cnumdict:
            missingchecks.append(str(i))

    WindowUtils.popup_message_ok(s, 'There are '+str(len(missingchecks))+' missing checks.', sw, log)
    return missingchecks

# OLD FORMAT
def handle_cleared_unrecorded_checks():
    elemarray, contentarray, total = do_query_cleared_unrecorded_checks()
    if len(elemarray) > 0:
        do_transaction_list_window(elemarray, contentarray, 'Cleared, unrecorded checks'
                                   +(' Total='+str(total) if total else ''),
                                   True, False, do_query_cleared_unrecorded_checks)
    else:
        WindowUtils.popup_message_ok(s, 'There are no cleared, unrecorded checks at this time.', sw, log)

def handle_missing_unrecorded_checks():
    missingchecks = do_query_missing_unrecorded_checks()
    if len(missingchecks) == 0: return

    lmci = len(missingchecks)
    groupedmissingchecks = []
    for i in xrange(0, len(missingchecks), 5):
        groupedmissingchecks.append(
            '{} {} {} {} {}'.format(
                missingchecks[i],
                (missingchecks[i+1] if i+1 < lmci else ''),
                (missingchecks[i+2] if i+2 < lmci else ''),
                (missingchecks[i+3] if i+3 < lmci else ''),
                (missingchecks[i+4] if i+4 < lmci else '')))
    WindowUtils.popup_message_ok(s, groupedmissingchecks, sw, log, title=' Missing check numbers ')

def handle_uncleared_checks():
    query = do_uncleared_checks_query()
    elemarray, contentarray, total = get_check_data_array_and_content_array(query)
    if elemarray is None:
        WindowUtils.popup_message_ok(s, 'No uncleared checks', sw, log)
        return
    do_transaction_list_window(elemarray, contentarray, 'All uncleared checks since January 1, 2006',
                               False, True, get_check_data_array_and_content_array, query)

def handle_all_recorded_checks():
    query = do_check_all_query()
    elemarray, contentarray, total = get_check_data_array_and_content_array(query)
    if elemarray is None:
        WindowUtils.popup_message_ok(s, 'Nothing in the "checks" database', sw, log)
        return
    do_transaction_list_window(elemarray, contentarray, 'Total='+(str(total) if total else ''),
                               False, True, get_check_data_array_and_content_array, query)

def handle_transaction_search():
    table, field, isorlike, value = get_search_parameters()
    if not field: return

    # create the mysql query strings. Default is to match value case-sensitive.
    # The listquery may be for 'main' or 'checks'
    listquery, totalquery = get_search_query(table, field, isorlike, value, casesensitive=False)

    # Run the queries and get the results
    if table == 'main':
        elemarray, contentarray, total = get_data_array_and_content_array(listquery, totalquery)
    else:
        elemarray, contentarray, total = get_check_data_array_and_content_array(listquery)
    if not elemarray:
        WindowUtils.popup_message_ok(s, 'Nothing returned from search "'+listquery+'"', sw, log)
        return

    # Display the results and manage the window
    do_transaction_list_window(elemarray, contentarray, 'Total='+(str(total) if total else ''),
                               False, True, get_data_array_and_content_array, listquery, totalquery)

"""
A handler for a list of numrows items that begin at window offset topoflist.
When <enter> is hit, the item # is returned.
Returns entry # between 0 and numrows-1.
TODO: Inverse highlight the current item of the list
"""
def getListItem(topoflist, leftmargin, numrows, win, mywin=None):
    global s

    bottomoflist = topoflist + numrows - 1
    if mywin is not None and mywin.currx != 0:
        x = mywin.currx
        y = mywin.curry
    else:
        x = leftmargin
        y = topoflist

    if mywin is not None:
        mywin.win.move(y, x)
        mywin.curry, mywin.currx = win.getyx()
        mywin.draw_border()
    else:
        win.move(y, x)
        win.refresh()

    while True:
        i = s.getch()

        # 'f' brings up filter dialog, then queries the database and redraws window based on the filter
        # selected

        # short-cut: menu item number selection
        if numrows < 10:
            for n in range(0, numrows):
                if i == ord(str(n)):
                    return n, ''

        # 'j' moves the cursor down
        if i == ord('j'):
            y += 1
            if mywin is not None:
                if mywin.current_row(y - topoflist) >= len(mywin.contents):
                    y -= 1
                elif y > bottomoflist:
                    y = bottomoflist
            else:
                if y > bottomoflist: y = bottomoflist

        # 'k' moves the cursor up
        if i == ord('k'):
            y -= 1
            if y < topoflist: y = topoflist

        # 'p' moves to the previous page
        if i == ord('p'): # previous page if a mywin
            if mywin is not None:
                currpage = mywin.currpage
                currpage -= 1
                if currpage >= 1:
                    mywin.currpage = currpage
                    x = 1
                    y = mywin.height-2 # go to bottom of the next page
                    mywin.draw_contents()

        # 'n' moves to the next page
        if i == ord('n'): # next page if a mywin
            if mywin is not None:
                currpage = mywin.currpage
                currpage += 1
                if currpage <= mywin.pages:
                    mywin.currpage = currpage
                    x = 1
                    y = 1 # go to top of the next page
                    mywin.draw_contents()

        # 'q' quits the window
        if i == ord('q'):
            return y - topoflist, 'quit'

        # '<enter>' selects the current item for editing
        if i == ord('\n'):
            if mywin is not None:
                return mywin.current_row(y - topoflist), ''
            else:
                return y - topoflist, ''

        # redraw or bring up window from previous command
        try:
            if mywin is not None:
                mywin.win.move(y, x)
                mywin.curry, mywin.currx = win.getyx()
                mywin.draw_border()
            else:
                win.move(y, x)
                win.refresh()
        except:
            quit('getListItem win.move({},{}) exception'.format(y, x))

def globalExceptionHandler(exctype, value, tb):
    trs = ''
    for tr in traceback.format_list(traceback.extract_tb(tb)):
        trs += tr
    quit('**********************************\nException occured\nType: '
         +str(exctype)+'\nValue: '+str(value)+'\nTraceback:\n'+trs
         +'*********************************')

global sw, log

# Handle all exceptions
sys.excepthook = globalExceptionHandler

# Handle ctrl-c
signal.signal(signal.SIGINT, signal_handler)

# Open a connection to the database (accesses official budget database)
budDB = budgetDB('localhost', 'root', 'sawtooth', 'officialBudget')

if len(sys.argv) > 1:
    year = sys.argv[1]
else:
    print 'Usage '+sys.argv[0]+' <year>'
    sys.exit(1)

s = init_screen()

# Present a list of menu items, then have the user choose one
sw = ScreenWindow(s)
WindowList.initialize(s)

log = open('log', 'w')

menus = ['Select by budget category for given year',
         'Select by budget category for all years',
         'Select by year-month',
         'Select checks by budget category for given year',
         'Select checks by budget category for all years',
         'Select checks by year-month',
         'Add uncleared checks',
         'Add cleared checks',
         'All recorded checks',
         'All uncleared checks',
         'All missing/unrecorded checks',
         'Search transactions',
         'Quit']

sw.draw_menu(menus)

while True:
    entry, command = getListItem(1, 1, len(menus), s)
    # if quit selected, affirm
    if command == 'quit' or 'quit' in menus[entry].lower():
        response = WindowUtils.popup_get_yes_no(s, 'Really quit?', sw, log, default='NO')
        if response.lower() == 'yes':
            break
    elif 'Select by budget category for given' in menus[entry]:
        # manage all non-check transactions for the given budget category for
        # this year
        budcat = WindowUtils.popup_get_text(s, 'What is the budget category?', sw, log)
        handle_edit_budget_by_budcat_both(budcat, theYear=year)
    elif 'Select by budget category for all' in menus[entry]:
        # manage all non-check transactions for the given budget category for
        # all years
        budcat = WindowUtils.popup_get_text(s, 'What is the budget category?', sw, log)
        handle_edit_budget_by_budcat_both(budcat)
    elif 'Select by year' in menus[entry]:
        # manage all non-check transactions for the given year and month
        yearmonth = WindowUtils.popup_get_text(s, 'Enter the year and month as yyyy-mm', sw, log)
        handle_edit_budget_by_month_both(yearmonth)
    elif 'Select checks by budget category for given' in menus[entry]:
        # manage all check transactions for a given budget category for this
        # year
        budcat = WindowUtils.popup_get_text(s, 'What is the budget category?', sw, log)
        handle_edit_check_by_budcat(budcat, theYear=year)
    elif 'Select checks by budget category for all' in menus[entry]:
        # manage all check transactions for a given budget category for all
        # years
        budcat = WindowUtils.popup_get_text(s, 'What is the budget category?', sw, log)
        handle_edit_check_by_budcat(budcat)
    elif 'Select checks by year' in menus[entry]:
        # manage all check transactions for the given year and month
        yearmonth = WindowUtils.popup_get_text(s, 'Enter the year and month as yyyy-mm', sw, log)
        handle_edit_check_by_month(yearmonth)
    elif 'Add un' in menus[entry]: # Add uncleared checks
        do_add_check()
    elif 'Add cl' in menus[entry]: # Add cleared checks
        handle_cleared_unrecorded_checks()
    elif 'All mi' in menus[entry]: # Add cleared checks
        handle_missing_unrecorded_checks()
    elif 'All uncl' in menus[entry]:
        handle_uncleared_checks()
    elif 'All re' in menus[entry]:
        # manage all recorded check transactions for all years
        handle_all_recorded_checks()
    elif 'Search tr' in menus[entry]:
        # manage all non-check transactions that match the search criteria
        handle_transaction_search()

quit('Quit selected')

