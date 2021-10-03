#!/usr/local/bin/python3

"""Edit budget categories module"""

# This module is too big - too many statements
from __future__ import print_function
import sys
from itertools import chain
import math
import datetime
import curses
import signal
import traceback
import WindowUtils
import WindowList

from budgetQueries import BudgetDB
from editWindow import EditWindow
from Window import ScreenWindow
from mysettings import g

TOTAL_FORMAT = '${:0,.2f}'


def signal_handler(caught_signal, frame):
    """Called whenever a CTRL-C is sent to the process -- quit gracefully.

    :param int caught_signal: the signal that was caught and brought us here
    :param Any frame: the stack frame
    """
    ScreenWindow.my_quit('Exit forced -- nothing saved')


def new_transaction():
    """Called for new check transactions only.

    :returns: a new, initialized transaction dictionary
    :rtype: dict
    """
    _new_transaction = list()

    # checks
    _new_transaction.append(None)     # tdate
    _new_transaction.append('')       # tnum
    _new_transaction.append('')       # tpayee
    _new_transaction.append('')       # tchecknum
    _new_transaction.append('b')      # ttype
    _new_transaction.append(0.0)      # tamt

    bud = list()
    bud.append(['UNKNOWN', 0.0, None])
    _new_transaction.append(bud)      # budarray

    _new_transaction.append('')       # comments
    _new_transaction.append(None)     # clear_date

    return _new_transaction


def do_add_check(my_entry=None, add_anyway=False):
    """Handle calling the check editor window and returning if there were changes.

    :param dict my_entry: (optional) check transaction dictionary to add
    :param bool add_anyway: (optional) whether to add check regardless or not
    :rtype: bool
    """
    win = EditWindow(bud_db, 3, curses.COLOR_BLUE, curses.COLOR_YELLOW)
    win.create(20, 80, title='Add Check')
    WindowList.add_window(win.win)
    win.win.bkgd(' ', curses.color_pair(3))

    if my_entry is None:
        # Create a new, empty, transaction
        my_entry = new_transaction()
        new = True
    else:
        if add_anyway:
            new = True
        else:
            new = False

    WindowUtils.popup_message_ok('do_add_check(): '+str(my_entry))

    win.draw_win(False,  # isMain
                 my_entry[g.tDate],  # transaction date
                 my_entry[g.tPayee],  # transaction payee
                 str(my_entry[g.tCkn]),  # transaction check number
                 my_entry[g.tAmount],  # transaction amount
                 my_entry[g.tBudarr],  # transaction budget list of lists
                 my_entry[g.tComment],  # transaction comment, if any
                 my_entry[g.tClearDate])  # check clear date

    changes = win.check_event_loop(my_entry, new)  # manage the edit window until quit is requested

    win.delete()  # delete the window
    return changes


def do_edit_win(my_entry):
    """Handle editing a transaction

    The entry is either a check entry or a main table entry. It now handles multi-budget transactions.
    It returns whether there were changes or not.

    :param dict my_entry: The transaction dictionary to edit
    :rtype: bool
    """
    is_check = my_entry[g.tCkn] > 0
    is_main = not is_check

    # Where did this entry come from?
    if is_check and len(my_entry) > g.tClearDate:
        # this is a check from the 'checks' table (which has a cleardate field)
        from_checks = True
    else:
        # this is an entry from the 'main' table (check or not: has no cleardate field)
        from_checks = False

    read_only = is_check and not from_checks

    win = EditWindow(bud_db, 4, curses.COLOR_BLACK, curses.COLOR_CYAN)

    if read_only:
        my_title = 'VIEW ONLY - check from main table'
    else:
        my_title = 'Edit '+('check' if is_check else 'main')+' transaction budget'

    win.create(40, 80, title=my_title)
    WindowList.add_window(win.win)
    win.win.bkgd(' ', curses.color_pair(4))
    if is_main:
        win.draw_win(True,  # is_main
                     my_entry[g.tDate],  # transaction date
                     my_entry[g.tPayee],  # transaction payee
                     my_entry[g.tType],  # transaction type
                     my_entry[g.tAmount],  # transaction amount
                     my_entry[g.tBudarr],  # transaction budget list of lists
                     my_entry[g.tComment],  # transaction comment, if any
                     '')                # extra field (for main only)

    # Sometimes this function is called with entry coming from a 'main' table
    # query but of a check. That entry won't have a cleardate field because
    # it's from the 'main' table. Replace that field with 'xxx'.
    else:
        win.draw_win(False,  # is_main
                     my_entry[g.tDate],  # transaction date
                     my_entry[g.tPayee],  # transaction payee
                     str(my_entry[g.tCkn]),  # transaction check number
                     my_entry[g.tAmount],  # transaction amount
                     my_entry[g.tBudarr],  # transaction budget list of lists
                     my_entry[g.tComment],  # transaction comment, if any
                     (my_entry[g.tClearDate] if from_checks else None))  # check cleared date
        #  (check only)

    changes = win.main_event_loop(is_main, my_entry, readonly=read_only)

    win.delete()
    return changes


def do_edit_win_both(my_entry):
    """Handle editing a transaction

    The entry is either a check entry or a main table entry. It now handles multi-budget transactions.
    It returns whether there were changes or not.

    :param dict my_entry: The transaction dictionary to edit
    :rtype: bool
    """
    is_check = my_entry[g.tCkn] > 0
    is_main = not is_check

    win = EditWindow(bud_db, 4, curses.COLOR_BLACK, curses.COLOR_CYAN)
    win.create(40, 80, title='Edit '+('check' if is_check else 'main')+' transaction budget')
    WindowList.add_window(win.win)
    win.win.bkgd(' ', curses.color_pair(4))
    if is_main:
        win.draw_win(True,  # is_main True => is_check False
                     my_entry[g.tDate],  # transaction date
                     my_entry[g.tPayee],  # transaction payee
                     my_entry[g.tType],  # transaction type
                     my_entry[g.tAmount],  # transaction amount
                     my_entry[g.tBudarr],  # transaction budget list of lists
                     my_entry[g.tComment],  # transaction comment (if any)
                     '')                 # unused
    else:
        win.draw_win(False,  # is_main False => is_check True
                     my_entry[g.tDate],  # transaction date
                     my_entry[g.tPayee],  # transaction payee
                     str(my_entry[g.tCkn]),  # transaction check number
                     my_entry[g.tAmount],  # transaction amount
                     my_entry[g.tBudarr],  # transaction budget list of lists
                     my_entry[g.tComment],  # transaction comment (if any)
                     my_entry[g.tClearDate])  # check clear date

    changes = win.main_event_loop(is_main, my_entry)

    win.delete()
    return changes


def get_search_parameters():
    """Handle the search transactions menu item.

     Return tuple of table, field, compare type, and value.

     :rtype: tuple
     """
    table = WindowUtils.popup_get_multiple_choice('Select one of the tables:', ['main', 'checks'], '')

    columns = 0
    if table == 'main':
        columns = bud_db.main_columns
    elif table == 'checks':
        columns = bud_db.checks_columns

    field = WindowUtils.popup_get_multiple_choice_vert(f"Select one of the columns from table: {table}", columns, "")
    if not field.upper() in columns:
        WindowUtils.popup_message_ok(f"No such field '{field}' in table '{table}': {columns}")
        return '', '', '', ''

    compare = WindowUtils.popup_get_multiple_choice('Select comparison:', ['equals', 'like'], '').strip()
    if compare.lower() == 'equals':
        compare = '='

    if field.lower() == 'bud_category' and compare == '=':
        value = WindowUtils.popup_get_multiple_choice_vert('Select a budget category:', bud_db.bud_cat_list, '')
    else:
        value = WindowUtils.popup_get_text('Enter the value to search for:')

    return table, field, compare, value


def do_transaction_list_window(
        data_array, content_array, total, my_title, add_edit, last_page, q_func, *args):
    """Handle the transaction list window: scrolling, paging, selecting, updating.

    :param list data_array: the window contents as list of data values
    :param list content_array: the window contents as list of strings
    :param float total: The total of the items in the list
    :param str my_title: the window title. Must have TOTAL_FORMAT (or at least '{}') somewhere in it for
     the total value
    :param bool add_edit: if True, add the transaction to the DATABASE; if not, edit either as a main
    transaction or checks transaction
    :param bool last_page: passed to drawContents
    :param types.FunctionType q_func: function to requery the data_array and contents_array
    :param Any args: arguments for q_func
    """
    num_rows = len(content_array)
    list_win = EditWindow(bud_db, 2, curses.COLOR_BLACK, curses.COLOR_GREEN)

    win_rows = min(num_rows, list_win.s_height - 5)
    list_win.create(win_rows + 2, 120, title=my_title.format(total).replace('$-', '-$'))
    WindowList.add_window(list_win.win)
    list_win.win.bkgd(' ', curses.color_pair(2))
    list_win.contents = content_array
    list_win.pages = int(math.ceil(len(content_array) / float(list_win.height - 2)))
    list_win.draw_contents(last_page=last_page)  # readContentLines is called in draw_contents()

    # check number is 0 for main transactions display the list of transactions
    while True:
        # handle navigation and selection of window list - returns row number of selection
        entry_index, my_command = get_list_item(1, 1, win_rows, list_win.win, my_win=list_win)
        if my_command == 'quit':
            list_win.delete()
            return

        if add_edit:
            resp = do_add_check(my_entry=data_array[entry_index], add_anyway=True)
        elif len(args) == 4:  # main and check transactions are combined edit the selected list item,
            # either check or main -- This may change the contents of this window
            resp = do_edit_win_both(data_array[entry_index])
        else:
            # edit the selected list item -- This may change the contents of this window
            resp = do_edit_win(data_array[entry_index])

        # There were changes made so re-query the DATABASE and update the list_win contents and data
        # arrays (and window title)
        if resp:
            data_array, content_array, total = q_func(*args)

            if not content_array:
                list_win.delete()
                return

            list_win.set_title(my_title.format(total).replace('$-', '-$'))
            list_win.contents = content_array
            list_win.pages = int(math.ceil(len(content_array) / float(list_win.height - 2)))
        else:
            # redraw the list window contents after edit window is deleted
            list_win.draw_contents()
            WindowUtils.popup_message_ok('No changes made in edit window')

        # redraw the list window contents after edit window is deleted
        list_win.draw_contents()


def get_budcat_query(my_bud_cat, the_year):
    """Return two queries of main for budget categories. The first will return a set of transactions
    matching the criteria; the second returns the sum of the transaction amounts for that set.

    :param str my_bud_cat: the category to query for
    :param str the_year: the year to search the category for
    :rtype: tuple
    """
    if not my_bud_cat:
        my_bud_cat = 'UNKNOWN'

    my_bud_cat = my_bud_cat.upper()

    if my_bud_cat == 'ALL':
        if the_year == 'all':
            return ("select * from main where tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;",
                    "select sum(bud_amount) from main where tran_checknum = '0' and tran_desc not like "
                    "'CHECK %' order by bud_date;")
        return (f"select * from main where bud_date between '{the_year}-01-01' and '{the_year}-12-31' "
                "and tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;",
                f"select sum(bud_amount) from main where bud_date between '{the_year}-01-01' and '{the_year}-12-31' "
                "and tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;")
    else:
        if the_year == 'all':
            return (f"select * from main where bud_category = '{my_bud_cat}' and tran_checknum = '0' "
                    "and tran_desc not like 'CHECK %' order by bud_date;",
                    f"select sum(bud_amount) from main where bud_category = '{my_bud_cat}' and tran_checknum = '0' "
                    "and tran_desc not like 'CHECK %' order by bud_date;")
        return (f"select * from main where bud_category = '{my_bud_cat}' and bud_date between '{the_year}-01-01' "
                f"and '{the_year}-12-31' and tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;",
                f"select sum(bud_amount) from main where bud_category = '{my_bud_cat}' and bud_date "
                f"between '{the_year}-01-01' and '{the_year}-12-31' and tran_checknum = '0' and tran_desc not like "
                "'CHECK %' order by bud_date;")


def get_check_budcat_query(my_bud_cat, the_year):
    """Return two queries of checks for budget categories. The first will return a set of transactions
    matching the criteria; the second returns the sum of the transaction amounts for that set.

    :param str my_bud_cat: the category to query for
    :param str the_year: the year to search the category for
    :rtype: str
    """
    if not my_bud_cat:
        my_bud_cat = 'UNKNOWN'
    my_bud_cat = my_bud_cat.upper()
    if my_bud_cat == 'ALL':
        if the_year == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks order by bud_date;")
        return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                f"comments from checks where bud_date between '{the_year}-01-01' and '{the_year}-12-31' "
                "order by bud_date;")
    else:
        if the_year == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    f"comments from checks where bud_cat = '{my_bud_cat}' order by bud_date;")
        return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                f"comments from checks where bud_cat = '{my_bud_cat}' and bud_date between '{the_year}-01-01' "
                f"and '{the_year}-12-31' order by bud_date;")


def get_check_budcat_query_as_main(my_bud_cat, the_year):
    """Same as get_check_budcat_query() above, but order the fields as get_budcat_query() for main.

    :param str my_bud_cat: the category to query for
    :param str the_year: the year to search the category for
    :rtype: tuple
    """
    if not my_bud_cat:
        my_bud_cat = 'UNKNOWN'
    my_bud_cat = my_bud_cat.upper()
    if my_bud_cat == 'ALL':
        if the_year == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    "comments from checks order by bud_date;",
                    "select sum(bud_amt) from checks;")
        return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                f"comments from checks where bud_date between '{the_year}-01-01' and '{the_year}-12-31' "
                "order by bud_date;",
                f"select sum(bud_amt) from checks where bud_date between '{the_year}-01-01' and '{the_year}-12-31';")
    else:
        if the_year == 'all':
            return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                    f"comments from checks where bud_cat = '{my_bud_cat}' order by bud_date;",
                    f"select sum(bud_amt) from checks where bud_cat = '{my_bud_cat}';")
        return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,"
                f"comments from checks where bud_cat = '{my_bud_cat}' and bud_date between '{the_year}-01-01' "
                f"and '{the_year}-12-31' order by bud_date;",
                f"select sum(bud_amt) from checks where bud_cat = '{my_bud_cat}' and bud_date between "
                f"'{the_year}-01-01' and '{the_year}-12-31' order by bud_date;")


def get_month_query(year_month):
    """Return two queries of main for transactions by year and month, and for sum of transaction amounts.

    :param str year_month: the year and month as 'yyyy-mm'
    :rtype: tuple
    """
    return (f'select * from main where bud_date like "{year_month}%" and tran_checknum = "0" and tran_desc not like '
            f'"CHECK %" order by bud_date;',
            f'select sum(bud_amount) from main where bud_date like "{year_month}%" and tran_checknum = "0" and '
            f'tran_desc not like "CHECK %" order by bud_date;')


def get_check_month_query(year_month):
    """Return one query of checks for transactions by year and month.

    :param str year_month: the year and month as 'yyyy-mm'
    :rtype: str
    """
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            f"checks where bud_date like '{year_month}' order by bud_date;")


def get_check_month_query_as_main(year_month):
    """Similar as get_month_query() above, but for checks.

    :param str year_month: the year and month as 'yyyy-mm'
    :rtype: tuple
    """
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            f"checks where bud_date like '{year_month}' order by bud_date;",
            f"select sum(bud_amt) from checks where bud_date like '{year_month}';")


def get_uncleared_checks_query():
    """Return mysql query to return all uncleared checks.

    :rtype: str
    """
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            "checks where clear_date is null and tdate > '2005-12-31' and tamt != 0 "
            "order by tdate,tchecknum;")


def get_check_all_query():
    """Return mysql query to return all recorded checks.

    :rtype: str
    """
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments from "
            "checks where tnum < 5000 order by tnum;")


def get_search_query(table, field, is_or_like, value, case_sensitive=True):
    """Return a query string based on 'field equals/like value', where value is matched case-sensitive
    or not.

    :param str table: the name of the table to run the query on
    :param str field: the name of the table field to compare value
    :param str is_or_like: a string containing '=' or 'like'
    :param str value: the value to match for the given field
    :param bool case_sensitive: whether to match on case or not. Default is True
    """
    if table == 'main':
        return (f"select * from main where {('BINARY ' if case_sensitive else '')}{field} {is_or_like} '{value}' "
                "order by bud_date;",
                f"select sum(bud_amount) from main where {('BINARY ' if case_sensitive else '')}{field} {is_or_like} "
                f"'{value}' order by bud_date;")
    return ("select tdate,tnum,tpayee,tchecknum,clear_date,tamt,bud_cat,bud_amt,bud_date,comments "
            f"from checks where {('BINARY ' if case_sensitive else '')}{field} {is_or_like} '{value}' "
            "order by bud_date;",
            f"select sum(bud_amt) from checks where {('BINARY ' if case_sensitive else '')}{field} {is_or_like} "
            f"'{value}' order by bud_date;")


def get_data_array_content_array(list_query, total_query):
    """Returns elem_array, content_array, total

    'elem_array' is a list of transactions retrieved directly from the database list_query
    Each transaction is
    tran_date, tran_ID, tran_desc, tran_checknum, tran_type, tran_amount, [array budget lists], comment
        0          1        2            3            4            5               6               7

    'content_array' is a list of formatted strings of each row retrieved from the DATABASE list_query
       (corresponds 1-to-1 with elem_array)
    'total' is the total of the individual transaction amounts for the list_query

    'list_query' returns 10 fields:
    tran_date, tran_ID, tran_desc, tran_checknum, tran_type, tran_amount, bud_category, bud_amount, bud_date, comment
        0         1         2             3           4           5            6             7         8         9

    Multi-budget transactions
    If tran_ID ends with '-\\d+', then the transaction is part of a multi-budget uber-transaction

    :param str list_query: mysql query string to return the list of transactions
    :param str total_query: mysql query string to return the total of transaction amounts in the list
    of transactions from the first query
    :rtype: tuple
    """

    # Do the list query
    cur = bud_db.execute_query(list_query)

    num_rows = cur.rowcount
    if num_rows == 0:
        return None, None, None

    # Fill out the elem_array and content_array
    elem_array = []
    content_array = []
    for row in cur:
        bud_array = list()
        try:
            transaction_id = row[g.tID].split('-')  # Check transaction ID for multi-budget tag
        except ValueError as ve:
            WindowUtils.popup_message_ok([f"transaction ID type ({str(type(row[g.tID]))}): <{ve}>, '{list_query}'"])
            return None, None, None

        # Handle multi-budget items
        if len(transaction_id) > 1 and transaction_id[-1].isdigit():

            # Create transaction ID without multi-budget part
            idx = row[g.tID].rfind('-')
            tran_id_pre = row[g.tID][:idx]

            # Do second query to grab all records matching the shortened transaction ID
            cur2 = bud_db.execute_query_2("select bud_category, bud_amount, bud_date from main where tran_ID like "
                                          f"'{tran_id_pre}-%' order by bud_date;")

            # Add all budget results to bud_array
            for brow in cur2:
                bud_array.append([brow[0], brow[1], brow[2]])
            the_bud = [row[6], row[7], row[8]]

        # Handle single budget items
        else:  # Put only one row in bud_array
            # The query returns 3 extra fields for each budget transaction.
            # These are combined into the bud_array.
            bud_array.append([row[6], row[7], row[8]])
            the_bud = [row[6], row[7], row[8]]

        # Create the entry in elem_array
        elem = [row[g.tDate],      # transaction date
                row[g.tID],        # transaction ID
                row[g.tPayee],     # transaction payee
                row[g.tCkn],       # transaction check number
                row[g.tType],      # transaction type
                row[g.tAmount],    # transaction amount
                bud_array,         # transaction budget list of lists
                row[g.tCommentQ]]  # transaction comment, if any
        elem_array.append(elem)

        # Create the entry in content_array. Multi-budget entries are displayed differently
        if len(bud_array) > 1:  # multi-budget
            content_row = '%-12s %4d %-40s %s %10.2f %-15s %s' % (
                (row[g.tDate].strftime('%m/%d/%Y') if row[g.tDate] else '---'),  # transaction date
                row[g.tCkn],                          # transaction check number
                row[g.tPayee][:40],                   # transaction description
                (row[g.tType] if 'str' in str(type(row[g.tType])) else 'b'),  # transaction type
                row[g.tAmount],                       # transaction amount
                'MULTI',                              # budget category
                row[g.tCommentQ])                     # transaction comment
        else:  # single budget
            content_row = '%-12s %4d %-40s %s %10.2f %-15s %s' % (
                (the_bud[2].strftime('%m/%d/%Y') if the_bud[2] else '---'),  # bud_date
                row[g.tCkn],                          # transaction check number
                row[g.tPayee][:40],                   # transaction description
                (row[g.tType] if 'str' in str(type(row[g.tType])) else 'b'),  # transaction type
                the_bud[1],                           # bud_amount
                the_bud[0],                           # bud_category
                row[g.tCommentQ])                     # transaction comment
        content_array.append(content_row)

    # Get the total of all entries using the total-query
    total = 0.0
    cur = bud_db.execute_query(total_query)
    for row in cur:
        total = row[0]

    # Return the results
    return elem_array, content_array, total


# This method is too complex: the name is too long, there are too many branches and too many lines.
def get_data_array_content_array_both(main_list_query, main_total_query, checks_list_query,
                                      checks_total_query):
    """Combines getting data arrays for both main and checks tables, and combines them together in one
    data array and content array, displayed mixed together. To do this more easily, the format of the
    checks query has changed so the fields between the two arrays match.

    :param str main_list_query: mysql query string to return the list of main transactions
    :param str main_total_query: mysql query string to return the total of main transaction amounts in
    the list
    :param str checks_list_query: mysql query string to return the list of checks transactions
    :param str checks_total_query: mysql query string to return the total of checks transaction amounts
    in the list
    :rtype: tuple
    """
    # Do the main list query
    cur = bud_db.execute_query(main_list_query)

    num_main_rows = cur.rowcount

    # Fill out the main_elem_array
    main_elem_array = []
    for row in cur:
        bud = list()  # list of lists - contains all budget arrays for the given transaction
        # (multi-budget can have more than one)
        transaction_id = row[g.tID].split('-')  # Check transaction ID for multi-budget tag

        # Handle multi-budget items
        if len(transaction_id) > 1 and transaction_id[-1].isdigit():
            # Create transaction ID without multi-budget part
            idx = row[g.tID].rfind('-')
            tran_id_pre = row[g.tID][:idx]

            # Do second query to grab all records matching the shortened transaction ID
            cur2 = bud_db.execute_query_2("select bud_category, bud_amount, bud_date from main where tran_ID like "
                                          f"'{tran_id_pre}-%' order by bud_date;")

            # Add all budget results to bud
            for brow in cur2:
                bud.append([brow[0], brow[1], brow[2]])
            the_bud = [row[6], row[7], row[8]]

        # Handle single budget items
        else:  # Put only one row in bud
            bud.append([row[6], row[7], row[8]])
            the_bud = [row[6], row[7], row[8]]

        # Create the entry in elem_array
        if not(g.tDate is None or bud[0][2] is None):
            elem = [row[g.tDate],      # transaction date
                    row[g.tID],        # transaction ID
                    row[g.tPayee],     # transaction description
                    row[g.tCkn],       # transaction check number
                    row[g.tType],      # transaction type
                    row[g.tAmount],    # transaction amount
                    bud,               # transaction budget list of lists
                    row[g.tCommentQ],  # transaction comment (if any)
                    '',                # filler field so both checks and main
                                       # elem_arrays have the same number of rows
                    the_bud]           # the one budget array to display
            main_elem_array.append(elem)

    # Do the checks list query
    cur = bud_db.execute_query(checks_list_query)

    num_checks_rows = cur.rowcount
    if num_main_rows + num_checks_rows == 0:
        return None, None, None

    # Fill out the checks_elem_array
    checks_elem_array = []
    for row in cur:
        bud = list()

        transaction_id = row[g.tID].split('-')
        # is multi-budget. Fill the array of budget items with multiple elements
        if len(transaction_id) > 1 and transaction_id[-1].isdigit():
            idx = row[g.tID].rfind('-')
            tnum_pre = row[g.tID][:idx]
            cur2 = bud_db.execute_query_2("select bud_cat, bud_amt, bud_date from checks where tnum like "
                                          f"'{tnum_pre}-%' order by bud_date;")
            for brow in cur2:
                bud.append([brow[0], brow[1], brow[2]])
            the_bud = [row[6], row[7], row[8]]

        # is single-budget. Put only one row in the array of budget items
        else:
            bud.append([row[6], row[7], row[8]])
            the_bud = [row[6], row[7], row[8]]

        if not(g.tDate is None or bud[0][2] is None):
            elem = [row[g.tDate],      # transaction date
                    row[g.tID],        # transaction ID
                    row[g.tPayee],     # transaction payee
                    row[g.tCkn],       # transaction check number
                    'b',               # row[tType] is the clear_date -
                                       # overwriting with static transaction type
                    row[g.tAmount],    # transaction amount
                    bud,               # transaction budget list of lists
                    row[g.tCommentQ],  # transaction comment, if any
                    row[g.tType],      # check clear date
                    the_bud]           # the one budget array to display
            checks_elem_array.append(elem)

    # Combine arrays for both queries and sort on budget date (element 6,0,2)
    # TODO: need to sort by transaction date (x[0]) for multi-budget transactions
    # TODO: cannot sort null dates (all canceled checks) -- FIXED do not include transactions with
    #       null dates (transaction or budget) in elem_array

    # cool way to sort list of lists by element in sub-list
    elem_array = sorted(main_elem_array+checks_elem_array, key=lambda x: x[9][2])

    content_array = []
    for row in elem_array:
        the_bud = row[9]
        # Create the entry in content_array. Multi-budget entries are displayed differently
        if len(row[g.tBudarr]) > 1:  # multi-budget
            content_row = '%-12s %-40s %4s %s %10.2f %-15s %s' % (
                (the_bud[2].strftime('%m/%d/%Y')
                 if not the_bud[2] is None else '---'),  # budget date
                row[g.tPayee][:40],  # transaction description
                row[g.tCkn],         # transaction check number (if any)
                row[g.tType],        # transaction type
                the_bud[1],          # budget amount
                the_bud[0],          # budget category
                row[g.tComment])     # transaction comment
        else:  # single-budget
            content_row = '%-12s %-40s %4s %s %10.2f %-15s %s' % (
                (the_bud[2].strftime('%m/%d/%Y')
                 if not the_bud[2] is None else '---'),  # budget date
                row[g.tPayee][:40],  # transaction description
                row[g.tCkn],         # transaction check number (if any)
                row[g.tType],        # transaction type
                the_bud[1],          # budget amount
                the_bud[0],          # budget category
                row[g.tComment])     # transaction comment (if any)
        content_array.append(content_row)

    # Get the total of all entries using the total_query
    total = 0.0
    cur = bud_db.execute_query(main_total_query)
    for row in cur:
        if row[0]:
            total = float(row[0])
    cur = bud_db.execute_query(checks_total_query)
    for row in cur:
        if row[0]:
            total += float(row[0])

    # Return the results
    return elem_array, content_array, total


def get_check_data_and_content_array(query):
    """Returns elem_array, content_array, total

    'elem_array' is a list of 10 element arrays retrieved directly from the DATABASE query
    'elem_array' is a list of transactions retrieved directly from the DATABASE query
    'content_array' is a list of formatted strings of each row retrieved from the DATABASE 'list_query'
       (corresponds 1-to-1 with 'elem_array')

    'query' returns 10 fields (OLD FORMAT):
    tnum, tchecknum, tamt, tdate, tpayee, bud_cat, bud_amt, bud_date, comments, clear_date
    0       1        2     3       4       5        6         7        8           9
    :param str query: the query to get the transactions
    :rtype: tuple
    """
    cur = bud_db.execute_query(query)
    num_rows = cur.rowcount
    if num_rows == 0:
        return None, None, None

    elem_array = []
    content_array = []
    total = 0.0
    for row in cur:
        bud_array = list()
        transaction_id = row[g.tID].split('-')

        # is multi-budget. Fill the array of budget items with multiple elements
        if len(transaction_id) > 1 and transaction_id[-1].isdigit():
            idx = row[g.tID].rfind('-')
            tnum_pre = row[g.tID][:idx]
            cur2 = bud_db.execute_query_2("select bud_cat,bud_amt,bud_date from checks where tnum like "
                                          f"'{tnum_pre}-%' order by bud_date;")
            for brow in cur2:
                bud_array.append([brow[0], brow[1], brow[2]])
            the_bud = [row[6], row[7], row[8]]

        else:  # is single-budget. Put only one row in the array of budget items
            bud_array.append([row[6], row[7], row[8]])
            the_bud = [row[6], row[7], row[8]]

        elem = [row[g.tDate],        # transaction date
                row[g.tID],          # transaction ID
                row[g.tPayee],       # transaction payee
                row[g.tCkn],         # transaction check number
                'b',                 # transaction type
                row[g.tAmount],      # transaction amount
                bud_array,           # transaction budget list of lists
                row[g.tCommentQ],    # transaction comment, if any from query
                row[g.tClearDateQ]]  # check clear date from query
        elem_array.append(elem)
        total = total + (float(row[g.tAmount]) if row[g.tAmount] else 0.0)

        # multi-budget tdate tckn tpayee tamt cleardate bud_cat comments
        if len(bud_array) > 1:
            content_row = '%-12s %-6d %-40s %10.2f %-12s %-15s %s' % (
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
            content_row = '%-12s %-6d %-40s %10.2f %-12s %-15s %s' % (
                (row[g.tDate].strftime('%m/%d/%Y')
                 if row[g.tDate] is not None else '---'),
                row[g.tCkn],
                row[g.tPayee][:40],
                (row[g.tAmount] if row[g.tAmount] else 0.0),
                (row[g.tClearDateQ].strftime('%m/%d/%Y')
                 if row[g.tClearDateQ] is not None else '---'),
                the_bud[0],
                row[g.tCommentQ])
        content_array.append(content_row)

    return elem_array, content_array, total


def handle_edit_budget_by_budcat_both(my_bud_cat, the_year='all'):
    """Handles the editing of budget transactions by budget category for both main and checks.

    :param str my_bud_cat: name of budget to query for
    :param str the_year: the year to filter the query with (default is all years)
    """
    list_query, total_query = get_budcat_query(my_bud_cat, the_year)

    # query to return checks with fields in same order as main query
    check_list_query, check_total_query = get_check_budcat_query_as_main(my_bud_cat, the_year)

    elem_array, content_array, total = get_data_array_content_array_both(list_query, total_query, check_list_query,
                                                                         check_total_query)

    # elem_array is empty
    if not elem_array:
        WindowUtils.popup_message_ok(f"Budget category '{my_bud_cat}' is not in the DATABASE for year '{the_year}'")
        return

    do_transaction_list_window(elem_array, content_array, total,
                               f"Budcat={my_bud_cat},Year={the_year} Total={TOTAL_FORMAT}",
                               False, False, get_data_array_content_array_both, list_query,
                               total_query, check_list_query, check_total_query)


def handle_edit_budget_by_month_both(year_month):
    """Handles the editing of budget transactions by year and month for both main and checks.

    :param str year_month: the year and month to query for as 'yyyy-mm'
    """
    try:
        datetime.datetime.strptime(f"{year_month}-01", '%Y-%m-%d')
    except ValueError as ve:
        WindowUtils.popup_message_ok(f"User entered '{year_month}': {ve}")
        return

    list_query, total_query = get_month_query(year_month)
    check_list_query, check_total_query = get_check_month_query_as_main(year_month)
    elem_array, content_array, total = get_data_array_content_array_both(
        list_query, total_query, check_list_query, check_total_query)

    if elem_array is None:
        WindowUtils.popup_message_ok(f"Month '{year_month}' is not in the DATABASE")
        return

    do_transaction_list_window(elem_array, content_array, total, f"Month={year_month} Total={TOTAL_FORMAT}",
                               False, False, get_data_array_content_array_both, list_query,
                               total_query, check_list_query, check_total_query)


def handle_edit_check_by_budget_category(budget_category, the_year='all'):
    """Handle the editing of check transactions by budget category.

    :param str budget_category: the budget category to query for
    :param str the_year: the year to filter the query by (default is all years)
    """
    query = get_check_budcat_query(budget_category, the_year)
    elem_array, content_array, total = get_check_data_and_content_array(query)
    if elem_array is None:
        WindowUtils.popup_message_ok(f"Budget category '{budget_category}' is not in the 'checks' DATABASE for "
                                     f"year {the_year}")
        return
    do_transaction_list_window(elem_array, content_array, total,
                               f"Budcat={budget_category}, Year={the_year} Total={TOTAL_FORMAT}",
                               False, False, get_check_data_and_content_array, query)


def handle_edit_check_by_month(year_month):
    """Handle the editing of check transactions by year and month.

    :param str year_month: the year and month to query for as 'yyyy-mm'
    """
    try:
        datetime.datetime.strptime(f"{year_month}-01", "%Y-%m-%d")
    except ValueError as ve:
        WindowUtils.popup_message_ok(f"User entered '{year_month}': {ve}")
        return

    query = get_check_month_query(year_month)
    elem_array, content_array, total = get_check_data_and_content_array(query)
    if elem_array is None:
        WindowUtils.popup_message_ok(f"Month '{year_month}' is not in the 'checks' DATABASE")
        return
    do_transaction_list_window(elem_array, content_array, total,
                               f"Month={year_month} Total={TOTAL_FORMAT}",
                               False, False, get_check_data_and_content_array, query)


def do_query_cleared_unrecorded_checks():
    """Return the results of the cleared/unrecorded checks query as elem_array, content_array, my_total.

    :rtype: tuple
    """
    # elem_array is the list of cleared,unrecorded checks from the main table
    elem_array = []

    # content_array is the list of strings that are displayed in the window
    content_array = []

    # tnum, tchecknum, tamt, tdate, tpayee, bud_cat, bud_amt, bud_date, comments, clear_date
    #  0       1        2      3       4       5        6        7         8          9
    cur = bud_db.execute_query('select tran_checknum,tran_date,tran_amount from main where '
                               'tran_checknum != "0" and tran_type = "b" order by tran_checknum;')
    my_total = 0.0

    # for every cleared CU check, see if it also exists as a transaction in the checks DATABASE, with at
    # least an amount
    for row in cur:
        cur2 = bud_db.execute_query_2(f"select tchecknum from checks where tchecknum = '{str(row[0])}' "
                                      "and tamt is not null;")
        if cur2.rowcount == 0:  # The row is a cleared, unrecorded check
            check_entry = []
            bud_array = list()
            check_entry.append(None)         # tdate is None because the check's transaction date is not
                                             # known at this time
            check_entry.append(str(row[0]))  # tnum (varchar)
            check_entry.append('')           # tpayee (varchar), unknown
            check_entry.append(row[0])       # tchecknum (int)
            check_entry.append('b')          # ttype
            check_entry.append(row[2])       # tamt (decimal/float)
            bud_array.append(['', row[2], None])
            check_entry.append(bud_array)    # bud_array
            check_entry.append('')           # comments (varchar), unknown
            check_entry.append(row[1])       # clear_date is the main table's transaction date,
                                             # the date it cleared the bank
            elem_array.append(check_entry)
            content_array.append('%d %12s %7.2f' % (row[0], row[1].strftime('%m/%d/%Y'), row[2]))
            my_total += float(row[2])

    return elem_array, content_array, my_total


def do_query_missing_unrecorded_checks():
    """Return the results of the missing/unrecorded checks query as a list of check numbers.

    :rtype: list
    """
    c_num_dict = {}
    missing_checks = []
    cur = bud_db.execute_query('select tnum from checks where tnum < 5000 order by tnum;')
    first = True
    last_check = ''
    first_check = '0'
    for row in cur:
        if first:
            # some check numbers have hyphens (multi-budget). Only keep the check number part.
            first_check = row[0].split('-')[0]
            first = False
        c_num_dict[row[0].split('-')[0]] = True
        last_check = row[0].split('-')[0]

    # Check #s 2869-2929 and 3882-3989 are missing because of ordering new checkbooks and skipping these
    # ranges. Just skip them as they clutter up the real missing checks.
    for i in chain(range(int(first_check), 2869), range(2930, 3882), range(3990, int(last_check))):
        if str(i) not in c_num_dict:
            missing_checks.append(str(i))

    WindowUtils.popup_message_ok(f"There are {len(missing_checks)} missing checks.")
    return missing_checks


def handle_cleared_unrecorded_checks():
    """Handle cleared/unrecorded check transactions."""
    elem_array, content_array, total = do_query_cleared_unrecorded_checks()
    if elem_array:
        do_transaction_list_window(elem_array, content_array, total,
                                   f"Cleared, unrecorded checks Total={TOTAL_FORMAT}",
                                   True, False, do_query_cleared_unrecorded_checks)
    else:
        WindowUtils.popup_message_ok('There are no cleared, unrecorded checks at this time.')


def handle_missing_unrecorded_checks():
    """Handle missing/unrecorded check transactions."""
    missing_checks = do_query_missing_unrecorded_checks()
    if not missing_checks:
        return

    lmci = len(missing_checks)
    grouped_missing_checks = []
    for i in range(0, len(missing_checks), 5):
        grouped_missing_checks.append(
            '{} {} {} {} {}'.format(
                missing_checks[i],
                (missing_checks[i+1] if i+1 < lmci else ''),
                (missing_checks[i+2] if i+2 < lmci else ''),
                (missing_checks[i+3] if i+3 < lmci else ''),
                (missing_checks[i+4] if i+4 < lmci else '')))
    WindowUtils.popup_message_ok(grouped_missing_checks, title=' Missing check numbers ')


def handle_uncleared_checks():
    """Handle uncleared check transactions."""
    query = get_uncleared_checks_query()
    elem_array, content_array, total = get_check_data_and_content_array(query)
    if elem_array is None:
        WindowUtils.popup_message_ok('No uncleared checks')
        return
    do_transaction_list_window(elem_array, content_array, total,
                               'All uncleared checks since January 1, 2006 (total='+TOTAL_FORMAT+')',
                               False, True, get_check_data_and_content_array, query)


def handle_all_recorded_checks():
    """Handle all recorded check transactions."""
    query = get_check_all_query()
    elem_array, content_array, total = get_check_data_and_content_array(query)
    if elem_array is None:
        WindowUtils.popup_message_ok('Nothing in the "checks" DATABASE')
        return
    do_transaction_list_window(elem_array, content_array, total, 'Total='+TOTAL_FORMAT,
                               False, True, get_check_data_and_content_array, query)


def handle_transaction_search():
    """Handle transaction search."""
    table, field, is_or_like, value = get_search_parameters()
    if not field:
        return

    # create the mysql query strings. Default is to match value case-sensitive.
    # The list_query may be for 'main' or 'checks'
    list_query, total_query = get_search_query(table, field, is_or_like, value, case_sensitive=False)

    # Run the queries and get the results
    if table == 'main':
        elem_array, content_array, total = get_data_array_content_array(list_query, total_query)
    else:
        elem_array, content_array, total = get_check_data_and_content_array(list_query)
    if not elem_array:
        WindowUtils.popup_message_ok(f"Nothing returned from search '{list_query}'")
        return

    # Display the results and manage the window
    do_transaction_list_window(elem_array, content_array, total, f"Total={TOTAL_FORMAT}",
                               False, True, get_data_array_content_array, list_query, total_query)


# This method is too complex: too many branches and too many statements.
def get_list_item(top_of_list, left_margin, num_rows, win, my_win=None):
    """A handler for a list of num_rows items that begin at window offset top_of_list.

    When <enter> is hit, the item # is returned.
    Returns entry # between 0 and num_rows-1.
    TODO: Inverse highlight the current item of the list

    :param int top_of_list: index of top of list
    :param int left_margin: the left side of list
    :param int num_rows: the number of list elements
    :param Any win: the window object containing the list
    :param Any my_win: not sure how this works
    """
    bottom_of_list = top_of_list + num_rows - 1
    if my_win and my_win.curr_x != 0:
        left = my_win.curr_x
        top = my_win.curr_y
    else:
        left = left_margin
        top = top_of_list

    if my_win:
        my_win.win.move(top, left)
        my_win.curr_y, my_win.curr_x = win.getyx()
        my_win.draw_border()
    else:
        win.move(top, left)
        win.refresh()

    while True:
        i = ScreenWindow.screen.getch()

        # 'f' brings up filter dialog, then queries the DATABASE and redraws window based on the filter
        # selected

        # short-cut: menu item number selection
        if num_rows < 10:
            for row_num in range(0, num_rows):
                if i == ord(str(row_num)):
                    return row_num, ''

        # 'j' moves the CURSOR down
        if i == ord('j'):
            top += 1
            if my_win:
                if my_win.current_row(top - top_of_list) >= len(my_win.contents):
                    top -= 1
                elif top > bottom_of_list:
                    top = bottom_of_list
            else:
                if top > bottom_of_list:
                    top = bottom_of_list

        # 'k' moves the CURSOR up
        if i == ord('k'):
            top -= 1
            if top < top_of_list:
                top = top_of_list

        # 'p' moves to the previous page
        if i == ord('p'):  # previous page if a my_win
            if my_win:
                current_page = my_win.current_page
                current_page -= 1
                if current_page >= 1:
                    my_win.current_page = current_page
                    left = 1
                    top = my_win.height - 2  # go to bottom of the next page
                    my_win.draw_contents()

        # 'n' moves to the next page
        if i == ord('n'):  # next page if a my_win
            if my_win:
                current_page = my_win.current_page
                current_page += 1
                if current_page <= my_win.pages:
                    my_win.current_page = current_page
                    left = 1
                    top = 1  # go to top of the next page
                    my_win.draw_contents()

        # 'q' quits the window
        if i == ord('q'):
            return top - top_of_list, 'quit'

        # '<enter>' selects the current item for editing
        if i == ord('\n'):
            if my_win:
                return my_win.current_row(top - top_of_list), ''
            return top - top_of_list, ''

        # redraw or bring up window from previous command
        try:
            if my_win:
                my_win.win.move(top, left)
                my_win.curr_y, my_win.curr_x = win.getyx()
                my_win.draw_border()
            else:
                win.move(top, left)
                win.refresh()
        except curses.error:
            ScreenWindow.my_quit(f"getListItem win.move({top},{left}) exception")


def global_exception_handler(exception_type, value, trace_back):
    """Handle all uncaught exceptions and print a useful quit message.

    :param types.ExceptionType exception_type: the type of exception caught
    :param int value: the value of the exception
    :param Any trace_back: contains stack trace
    """
    trs = ''
    for trace_back_element in traceback.format_list(traceback.extract_tb(trace_back)):
        trs += trace_back_element
    ScreenWindow.my_quit(f"**********************************\nException occurred\nType: {str(exception_type)}\n"
                         f"Value: {str(value)}\nTraceback:\n{trs}*********************************")


# pylint: disable-msg=C0103
bud_db = None
year = None


def main():
    """The main method. Used this way so internal methods can be used by other modules."""
    global bud_db, year

    # Handle all exceptions
    sys.excepthook = global_exception_handler

    # Handle ctrl-c
    signal.signal(signal.SIGINT, signal_handler)

    # Open a connection to the DATABASE (accesses official budget DATABASE)
    bud_db = BudgetDB('localhost', 'root', '', 'officialBudget')

    if len(sys.argv) > 1:
        year = sys.argv[1]
    else:
        print(f'Usage {sys.argv[0]} <year>')
        sys.exit(1)

    # init_screen() must be called to initialize the screen and log
    ScreenWindow.init_screen()

    # Present a list of menu items, then have the user choose one
    sw = ScreenWindow()
    WindowList.initialize()

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
        entry, command = get_list_item(1, 1, len(menus), ScreenWindow.screen)
        # if quit selected, affirm
        if command == 'quit' or 'quit' in menus[entry].lower():
            response = WindowUtils.popup_get_yes_no('Really quit?', default='NO')
            if response.lower() == 'yes':
                break
        elif 'Select by budget category for given' in menus[entry]:
            # manage all non-check transactions for the given budget category for
            # this year
            bud_cat = WindowUtils.popup_get_text('What is the budget category?')
            handle_edit_budget_by_budcat_both(bud_cat, the_year=year)
        elif 'Select by budget category for all' in menus[entry]:
            # manage all non-check transactions for the given budget category for
            # all years
            bud_cat = WindowUtils.popup_get_text('What is the budget category?')
            handle_edit_budget_by_budcat_both(bud_cat)
        elif 'Select by year' in menus[entry]:
            # manage all non-check transactions for the given year and month
            main_year_month = WindowUtils.popup_get_text('Enter the year and month as yyyy-mm')
            handle_edit_budget_by_month_both(main_year_month)
        elif 'Select checks by budget category for given' in menus[entry]:
            # manage all check transactions for a given budget category for this year
            bud_cat = WindowUtils.popup_get_text('What is the budget category?')
            handle_edit_check_by_budget_category(bud_cat, the_year=year)
        elif 'Select checks by budget category for all' in menus[entry]:
            # manage all check transactions for a given budget category for all years
            bud_cat = WindowUtils.popup_get_text('What is the budget category?')
            handle_edit_check_by_budget_category(bud_cat)
        elif 'Select checks by year' in menus[entry]:
            # manage all check transactions for the given year and month
            main_year_month = WindowUtils.popup_get_text('Enter the year and month as yyyy-mm')
            handle_edit_check_by_month(main_year_month)
        elif 'Add un' in menus[entry]:  # Add uncleared checks
            do_add_check()
        elif 'Add cl' in menus[entry]:  # Add cleared checks
            handle_cleared_unrecorded_checks()
        elif 'All mi' in menus[entry]:  # Add cleared checks
            handle_missing_unrecorded_checks()
        elif 'All uncl' in menus[entry]:
            handle_uncleared_checks()
        elif 'All re' in menus[entry]:
            # manage all recorded check transactions for all years
            handle_all_recorded_checks()
        elif 'Search tr' in menus[entry]:
            # manage all non-check transactions that match the search criteria
            handle_transaction_search()

    ScreenWindow.my_quit('Quit selected')


if __name__ == '__main__':
    main()
