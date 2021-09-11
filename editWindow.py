"""Module encapsulates methods relating to transaction edit windows"""
import curses
import datetime
import pymysql
import copy
from Window import MyWindow
from Window import ScreenWindow
import WindowUtils
from mysettings import g


class EditWindow(MyWindow):
    """Class to handle all editable windows

    :param BudgetDB bud_db: instance of database object
    :param int color_pair: a number to identify color schemes
    :param int fg_color: the foreground color of the window
    :param int bg_color: the background color of the window
    """

    def __init__(self, bud_db, color_pair, fg_color, bg_color):
        self.bud_db = bud_db
        self.color_pair = color_pair
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.balance = 0.0
        curses.init_pair(color_pair, fg_color, bg_color)
        super(EditWindow, self).__init__('edit')

    def draw_border(self):
        """Draw a border around me."""
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title)) // 2, self.title, curses.A_STANDOUT)
        self.win.addstr(0, self.width - 10, 'Page %d/%d' % (self.current_page, self.pages),
                        curses.A_STANDOUT)
        self.win.addstr(0, 2, 'Pos: %d,%d'%(self.curr_x, self.curr_y), curses.A_STANDOUT)
        self.win.move(self.curr_y, self.curr_x)
        self.win.refresh()
        self.log.write('draw_border[EditWindow] window (title='+self.title+')\n')

    def draw_win(self, is_main, transaction_date, transaction_description, transaction_type,
                 transaction_amount, budget_array, transaction_comment, extra_field):
        """Draw me as an edit window with the given values.

        :param bool is_main: whether the transaction is from the main table or the checks table
        :param Any transaction_date: the transaction date
        :param str transaction_description: the payee
        :param str transaction_type: a single character for which institution the transaction is from
        :param float transaction_amount: the transaction amount
        :param list budget_array: a list of budget entries (a 3-element list) for this transaction
        (can be multiple)
        :param str transaction_comment: a helpful comment; not from the original transaction, but
        added by a later user
        :param Any extra_field: for checks, this is the cleared date. Ignored for main transactions
        """
        self.win.clear()
        self.win.addstr(1, 1, 'Transaction date:')
        self.win.addstr(1, 20, (transaction_date.strftime('%m/%d/%Y') if transaction_date is not None
                                else '---'))
        if not is_main:
            self.win.addstr(1, 35, 'Cleared date:')
            self.win.addstr(1, 49, (extra_field.strftime('%m/%d/%Y') if extra_field is not None
                                    else '---'))
        self.win.addstr(2, 1, 'Description:')
        # Adding this field as editable
        self.win.addstr(2, 15, transaction_description[:60], curses.A_REVERSE)
        self.win.addstr(3, 1, ('Type:' if is_main else 'Chk#:'))
        self.win.addstr(3, 7, transaction_type)
        self.win.addstr(3, 15, 'Amount:')
        self.win.addstr(3, 23, '$%10.2f' % (transaction_amount if transaction_amount else 0))
        self.win.addstr(4, 1, 'Comments:')
        self.win.addstr(4, 11, transaction_comment, curses.A_REVERSE)
        self.win.addstr(6, 1, 'Budget items = ' + str(len(budget_array)))
        self.win.addstr(7, 1, 'Budget category')
        self.win.addstr(7, 18, 'Budget amount')
        self.win.addstr(7, 35, 'Budget date')
        row_num = 8
        self.balance = float(transaction_amount if transaction_amount else 0)
        for bud_list in budget_array:
            self.win.addstr(row_num, 1, bud_list[0], curses.A_REVERSE)
            self.win.addstr(row_num, 18, '%10.2f' % bud_list[1], curses.A_REVERSE)
            self.win.addstr(row_num, 35,
                            (bud_list[2].strftime('%m/%d/%Y') if bud_list[2] is not None else '---'),
                            curses.A_REVERSE)
            row_num += 1
            self.balance -= float(bud_list[1])
        self.win.addstr(6, 20, 'Balance: '+'%5.2f' % self.balance)
        self.draw_border()
        self.read_content_lines()
        self.log.write('draw_win[EditWindow] window (title='+self.title+')\n')

    def refresh(self, is_main, entry):
        """Redraw me.

        :param bool is_main: whether I am editing a main transaction or a check transaction
        :param dict entry: The dictionary containing my information
        """
        if is_main:
            self.draw_win(True,
                          entry[g.tDate],
                          entry[g.tPayee],
                          entry[g.tType],
                          entry[g.tAmount],
                          entry[g.tBudarr],
                          entry[g.tComment],
                          '')
        else:
            self.draw_win(False,
                          entry[g.tDate],
                          entry[g.tPayee],
                          str(entry[g.tClearDate]),
                          entry[g.tAmount],
                          entry[g.tBudarr],
                          entry[g.tComment],
                          entry[g.tClearDate])

    def get_list_of_budget_categories(self, table_name):
        return_list = []
        db_cursor = self.bud_db.execute_query('select bud_category from ' + table_name +
                                              ' group by bud_category;')
        for row in db_cursor.fetchall():
            return_list.append(row[0])
        return return_list

    def get_intended_value(self, entered_value, field_name):
        """Return string selected by user based on entered value.

        :param str entered_value: The value as entered by the user.
        :param str field_name: The name of the field where the value was entered.
        :rtype str:
        """
        values = []
        # Only supporting field "category" now; other fields just return entered_value.
        if field_name == 'category':
            values = self.get_list_of_budget_categories('main')
        else:
            return entered_value

        display_values = []
        # if something was entered, match values that begin with it
        if len(entered_value):
            for value in values:
                if value.lower().startswith(entered_value.lower()):
                    display_values.append(value)
            # if there were matches, insert entered_value at top
            if len(display_values):
                display_values.insert(0, entered_value.upper())
            # if there were no matches, ask if he wants to keep it or not
            else:
                ans = WindowUtils.popup_get_yes_no(f"No matching values. Use '{entered_value}'?")
                if ans.lower() == 'no':
                    return "unknown"
                else:
                    return entered_value

        # if nothing was entered, match all values
        else:
            display_values = values

        # if display_values has anything in it, display it.
        if len(display_values):
            choice = WindowUtils.popup_get_multiple_choice_vert('Choose an existing value',
                                                                display_values, display_values[0])
        # if display_values is empty (nothing matched), return entered_value (very rare)
        else:
            choice = entered_value

        return choice

    def main_event_loop(self, is_main, entry, readonly=False):
        """Handle keyboard events for this window.

        With the new combined main/checks transactions, the format of the checks entry is the same as the
        format of the main entry. This has implications in this function and in update_transaction.

        :param bool is_main: whether the entry is from the main table or the checks table
        :param dict entry: a dictionary of the transaction data
        :param bool readonly: whether this transaction can be edited or is read-only
        :rtype: bool
        """
        num_bud_entries = len(entry[g.tBudarr])
        tab_array = list()
        tab_array.append([15, 2, 'desc'])
        tab_array.append([11, 4, 'comments'])
        for i in range(8, 8+num_bud_entries): # range(first, last+1)
            tab_array.append([1, i, 'category'])
            tab_array.append([18, i, 'amount'])
            tab_array.append([35, i, 'date'])

        # all this call does is copy-by-value the entry to the returned list
        new_entry = self.update_transaction(entry, '', [])
        changes = False
        idx = 0

        #
        # Event Loop
        #
        while True:
            self.win.move(tab_array[idx][1], tab_array[idx][0])
            self.win.refresh()
            self.curr_y, self.curr_x = self.win.getyx()
            self.draw_border()

            i = ScreenWindow.screen.getch()
            if i == ord('\t'):
                idx = (idx + 1) % len(tab_array)
            #
            # Add a new, empty budget entry
            #
            elif i == ord('a') and not readonly:
                newguy = ['UNKNOWN', 0.00, datetime.datetime.today()]
                new_entry[g.tBudarr].append(newguy)
                newline = tab_array[-1][1]
                tab_array.append([1, newline+1, 'category'])
                tab_array.append([18, newline+1, 'amount'])
                tab_array.append([35, newline+1, 'date'])
                self.refresh(is_main, new_entry)
                changes = True
            #
            # Delete selected budget entry
            #
            elif i == ord('d') and not readonly:
                if tab_array[idx][1] < 8:  # MAGIC number
                    WindowUtils.popup_message_ok('You can only delete budget items.')
                    continue
                if len(new_entry[g.tBudarr]) < 2:  # MAGIC number
                    WindowUtils.popup_message_ok('You cannot delete the only budget item.')
                    continue
                row = tab_array[idx][1] - 8  # MAGIC number
                del new_entry[g.tBudarr][row]
                del tab_array[-1]  # delete last row (3 entries per row)
                del tab_array[-1]
                del tab_array[-1]

                # If the CURSOR was on the last line that got deleted
                if idx > len(tab_array)-1:
                    idx -= 3  # Move the CURSOR to the previous line
                self.refresh(is_main, new_entry)
                changes = True
            #
            # Change an existing record field
            #
            # edit current field
            elif (i == ord('r') or i == ord('e')) and not readonly:
                curses.echo()
                text = self.win.getstr().decode('utf8')  # read the value of the field in python3
                curses.noecho()

                # replace all " with ' because of the mysql update query will fail on " (it uses " to
                # delimit field values)
                text = text.replace('"', "'")

                # TODO: Check value of text against list of existing values of that field.
                # If the new entry does not match an existing value from the database,
                # suggest an existing value that is close, or take it as is.
                text = self.get_intended_value(text, tab_array[idx][2])

                new_entry = self.update_transaction(new_entry, text, tab_array[idx])
                self.refresh(is_main, new_entry)
                changes = True
            #
            # 'quit', saving all changes
            #
            elif i == ord('q'):
                if changes and not readonly:

                    # rounding errors will not produce an exact 0.00000
                    if abs(self.balance) >= 0.005:
                        WindowUtils.popup_message_ok(
                            ['Balance between transaction amount and sum of budget amounts is not '
                             'equal.', 'The difference is ${0:.2f}'.format(self.balance)])
                        continue
                    self.update_database(is_main, entry, new_entry)
                break  # keep value of 'changes' the same
            #
            # 'exit' without saving any changes
            #
            elif i == ord('x'):
                if changes:
                    answer = WindowUtils.popup_get_yes_no('There were changes. Exit without saving?',
                                                          default='NO')
                    if answer.lower() == 'no':
                        continue
                changes = False
                break

        return changes

    def check_event_loop(self, entry, add):
        """Handle keyboard events for the edit check window.

        :param dict entry: the original check entry dictionary
        :param bool add: whether or not a new entry, or update entry
        :rtype: bool
        """
        WindowUtils.popup_message_ok('check_event_loop(): add = '+str(add))
        num_bud_entries = len(entry[g.tBudarr])
        tab_array = [[19, 1, 'tdate'], [15, 2, 'tpayee'], [7, 3, 'checknum'], [23, 3, 'tamt'],
                     [11, 4, 'comments']]
        for i in range(8, 8+num_bud_entries):  # range(start, stop+1)
            tab_array.append([1, i, 'category'])
            tab_array.append([18, i, 'amount'])
            tab_array.append([35, i, 'date'])

        # all this call does is copy-by-value the entry (which itself can be an
        # empty transaction) to the returned list
        new_entry = self.update_transaction(entry, '', [])
        changes = False
        idx = 0
        while True:
            self.win.move(tab_array[idx][1], tab_array[idx][0])
            self.win.refresh()
            self.curr_y, self.curr_x = self.win.getyx()
            self.draw_border()
            i = ScreenWindow.screen.getch()
            if i == ord('\t'):
                idx = (idx + 1) % len(tab_array)
            if i == ord('r') or i == ord('e'):
                curses.echo()
                text = self.win.getstr().decode('utf8')  # read the value of the string in Python3
                curses.noecho()

                # replace all " with ' because of the mysql update query will fail on "
                # (it uses " to delimit field values)
                text = text.replace('"', "'")

                # Verify that the value of checknum is not already in the database and is an integer
                if tab_array[idx][2] == 'checknum':
                    db_cursor = self.bud_db.execute_query('SELECT * FROM checks WHERE tnum = "'
                                                          + text + '";')
                    num_rows = db_cursor.rowcount

                    # If it is in the database, notify and cancel
                    if num_rows > 0:
                        WindowUtils.popup_message_ok('Check number ' + text
                                                     + ' is already in the database')

                        # erase previous entry
                        self.win.addstr(tab_array[idx][1], tab_array[idx][0], '      ')
                        continue
                    try:
                        int(text)
                    except ValueError:
                        WindowUtils.popup_message_ok('Field "' + tab_array[idx][2] + '" value '
                                                     + text + ' is not an integer')

                        # erase previous entry
                        self.win.addstr(tab_array[idx][1], tab_array[idx][0], '      ')
                        continue

                # Verify that the value of tamt is a float
                elif tab_array[idx][2] == 'tamt' or tab_array[idx][2] == 'amount':
                    try:
                        float(text)
                    except ValueError:
                        WindowUtils.popup_message_ok('Field "' + tab_array[idx][2] + '" value '
                                                     + text + ' is not a float')

                        # erase previous entry
                        self.win.addstr(tab_array[idx][1], tab_array[idx][0], '             ')
                        continue

                # Verify that the value of tdate or budget date is a date (mm/dd/yyyy)
                elif tab_array[idx][2] == 'tdate' or tab_array[idx][2] == 'date':
                    try:
                        datetime.datetime.strptime(text, '%m/%d/%Y')
                    except ValueError:
                        WindowUtils.popup_message_ok('Field "' + tab_array[idx][2] + '" value '
                                                     + text + ' is not a date (mm/dd/yyyy)')

                        # erase previous entry
                        self.win.addstr(tab_array[idx][1], tab_array[idx][0], '          ')
                        continue

                new_entry = self.update_transaction(new_entry, text, tab_array[idx])
                self.draw_win(False, new_entry[g.tDate], new_entry[g.tPayee], str(new_entry[g.tCkn]),
                              new_entry[g.tAmount], new_entry[g.tBudarr], new_entry[g.tComment],
                              new_entry[g.tClearDate])
                changes = True
                idx = (idx + 1) % len(tab_array)
            if i == ord('q'):  # 'quit', saving any changes
                if changes:
                    # rounding errors will not produce an exact 0.00000
                    if abs(self.balance) >= 0.005:
                        WindowUtils.popup_message_ok(['Balance between transaction amount and sum of bud'
                                                      'get amounts is not equal.',
                                                      'The difference is ${0:.2f}'.format(self.balance)])
                        continue

                    # Somehow have to differentiate between an updated check record and a new record to
                    # be inserted.
                    if not new_entry[g.tID]:
                        WindowUtils.popup_message_ok('Transaction ID field is empty.')
                        continue
                    if new_entry[g.tAmount] == 0.0 and new_entry[g.tPayee].lower() != 'cancel':
                        WindowUtils.popup_message_ok('Transaction amount field is empty (and payee not "cancel").')
                        continue

                    if add:
                        # if add==True, then the original entry was empty
                        self.add_database(False, new_entry)
                    else:
                        # if add==False, then the original entry was full
                        self.update_database(False, entry, new_entry)

                break  # keep value of 'changes' the same

            if i == ord('x'):  # 'exit' without saving any changes
                if changes:
                    answer = WindowUtils.popup_get_yes_no('There were changes. Exit without saving?',
                                                          default='NO')
                    if answer.lower() == 'no':
                        continue
                changes = False
                break

        return changes

    def update_transaction(self, transaction, new_value, field_array):
        """Update transaction with any changes in new_value/field_array.

        Returns the new, updated transaction dictionary

        Apparently this method makes no reference to any class objects and so could be a static or
        class method or function instead of an instance method.

        :param dict transaction: the transaction dictionary (checks or main)
        :param str new_value: the new value of the named field
        :param list field_array: a 3-element array as [x-pos, y-pos, name]
        :rtype: dict
        """

        # copy everything by VALUE not by REFERENCE so changes made here don't ripple back to the
        # original
        new_transaction = copy.deepcopy(transaction)

        # All we wanted to do was make a copy of the incoming transaction
        # SIDE-EFFECT
        if not field_array:
            return new_transaction

        # Set from constants for field_array elements
        field_y = field_array[1]
        field_name = field_array[2]
        budget_entry = field_y - 8  # MAGIC NUMBER

        # Verify budget entry
        if budget_entry < 0 and (field_name == 'category' or field_name == 'amount'
                                 or field_name == 'date'):
            WindowUtils.popup_message_ok('field_name=' + field_name + ', but field_y < 8: '
                                         + str(field_y))
            return new_transaction

        bud_array = new_transaction[g.tBudarr]

        # Overwrite the field that changed
        if field_name == 'checknum':  # Checks only
            new_transaction[g.tCkn] = new_value

            # checknum and transaction num are the same
            new_transaction[g.tID] = new_value
        if field_name == 'tamt':  # Checks only
            try:
                amount = float(new_value)
                # Check amounts are ALWAYS negative
                amount = -1.0*abs(amount)

                # convert field back to floating point
                new_transaction[g.tAmount] = amount
            except ValueError:
                WindowUtils.popup_message_ok(f"'{new_value}' is not a float!")

        if field_name == 'tdate':  # Checks only
            try:
                # convert field back to date object
                new_transaction[g.tDate] = datetime.datetime.strptime(new_value, '%m/%d/%Y')
            except ValueError:
                WindowUtils.popup_message_ok('Bad date format. Expected format is m/d/yyyy')
                return new_transaction
        if field_name == 'tpayee':  # Checks only
            new_transaction[g.tPayee] = new_value
        if field_name == 'comments':  # Either main or checks
            new_transaction[g.tComment] = new_value
        if field_name == 'desc':  # Either main or checks
            new_transaction[g.tPayee] = new_value

        #
        # This section applies to the budget item(s) in the transaction, either main or checks
        #
        if field_name == 'category':
            # all budget categories are upper-case
            bud_array[budget_entry][0] = new_value.upper()
            new_transaction[g.tBudarr] = bud_array

        if field_name == 'amount':
            # convert field back to floating point
            try:
                bud_array[budget_entry][1] = float(new_value)
                new_transaction[g.tBudarr] = bud_array
            except ValueError:
                WindowUtils.popup_message_ok(f"'{new_value}' is not a float!")

        if field_name == 'date':
            try:
                # convert field back to date object
                bud_array[budget_entry][2] = datetime.datetime.strptime(new_value, '%m/%d/%Y')
            except ValueError:
                WindowUtils.popup_message_ok('Bad date format. Expected format is m/d/yyyy ('
                                             + new_value + ')')
                return new_transaction
            new_transaction[g.tBudarr] = bud_array

        return new_transaction  # return the new, changed transaction record

    def add_database(self, is_main, new_transaction):
        """This function adds new records to the database.

        :param bool is_main: whether new_transaction if from main or checks
        :param dict new_transaction: the new transaction to add to the database
        """
        #
        # First, find all the database records that match the tran_ID/tnum base
        # of the new transaction to add, and make sure there are none.
        #
        tid = new_transaction[g.tID]
        try:
            db_cursor = self.bud_db.execute_query('select * from ' + ('main' if is_main else 'checks')
                                                  + ' where ' + ('tran_ID' if is_main else 'tnum')
                                                  + ' like "' + tid + '%";')
        except pymysql.Error as excp:
            WindowUtils.popup_message_ok(f"mysql exception counting transaction database records with transaction id {tid}: {str(excp)}")
            return
        num_rows = db_cursor.rowcount
        if num_rows > 0:
            WindowUtils.popup_message_ok('There are already ' + str(num_rows) + ' rows in the database '
                                         'for transaction id ' + tid + ' that we want to add.')
            return

        #
        # Second, insert the records from the new_transaction into the database
        #
        new_multi = len(new_transaction[g.tBudarr]) > 1
        if new_multi:
            if is_main:
                i = 0
                for bud_array in new_transaction[g.tBudarr]:
                    query = ('insert into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran'
                             '_amount,bud_category,bud_amount,bud_date,comment) '
                             'values ("' + new_transaction[g.tDate].strftime('%Y-%m-%d') + '","'
                             + tid + '-' + str(i) + '","' + new_transaction[g.tPayee] + '","'
                             + str(new_transaction[g.tCkn]) + '","'
                             + new_transaction[g.tType] + '","'
                             + '{0:.2f}'.format(new_transaction[g.tAmount])
                             + '","' + bud_array[0] + '","'
                             + '{0:.2f}'.format(bud_array[1]) + '","'
                             + bud_array[2].strftime('%Y-%m-%d') + '","'
                             + new_transaction[g.tComment] + '");')
                    try:
                        self.bud_db.execute_query(query)
                    except pymysql.Error as excp:
                        WindowUtils.popup_message_ok([query, 'add_database()-main-multi:', 'mysql '
                                                      'exception inserting new multibudget '
                                                      'main transaction records:', str(excp)])
                        return
                    i += 1
            else:  # Checks
                i = 0
                for bud_array in new_transaction[g.tBudarr]:
                    query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_d'
                             'ate,comments,clear_date) values ("' + tid + '-' + str(i) + '","'
                             + str(new_transaction[g.tCkn]) + '","'
                             + '{0:.2f}'.format((new_transaction[g.tAmount]
                                                 if new_transaction[g.tAmount] else 0.0))
                             + '",' + ('"' + new_transaction[g.tDate].strftime('%Y-%m-%d') + '"'
                                       if new_transaction[g.tDate] else 'NULL')
                             + ',"' + new_transaction[g.tPayee] + '","'
                             + bud_array[0] + '","'
                             + '{0:.2f}'.format((bud_array[1] if bud_array[1] else 0.0)) + '",'
                             + ('"'+bud_array[2].strftime('%Y-%m-%d')+'"' if bud_array[2] else 'NULL')
                             + ',"' + bud_array[2].strftime('%Y-%m-%d') + '","'
                             + new_transaction[g.tComment] + '",'
                             + ('"' + new_transaction[g.tClearDate].strftime('%Y-%m-%d')
                                + '"' if new_transaction[g.tClearDate] else 'NULL') + ');')
                    try:
                        self.bud_db.execute_query(query)
                    except pymysql.Error as excp:
                        WindowUtils.popup_message_ok([query, 'add_database()-checks-multi:',
                                                      'mysql exception inserting new multibudget checks '
                                                      'transaction records:', str(excp)])
                        return
                    i += 1
        else:  # single budget items
            if is_main:
                query = ('insert into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran_amo'
                         'unt,bud_category,bud_amount,bud_date,comment) values ('
                         '"' + new_transaction[g.tDate].strftime('%Y-%m-%d') + '",'
                         '"' + new_transaction[g.tID] + '",'
                         '"' + new_transaction[g.tPayee] + '",'
                         '"' + str(new_transaction[g.tCkn]) + '",'
                         '"' + new_transaction[g.tType] + '",'
                         '"' + '{0:.2f}'.format(new_transaction[g.tAmount]) + '",'
                         '"' + new_transaction[g.tBudarr][0][0] + '",'
                         '"' + '{0:.2f}'.format(new_transaction[g.tBudarr][0][1]) + '",'
                         '"' + new_transaction[g.tBudarr][0][2].strftime('%Y-%m-%d') + '",'
                         '"' + new_transaction[g.tComment] + '");')
                try:
                    self.bud_db.execute_query(query)
                except pymysql.Error as excp:
                    WindowUtils.popup_message_ok([query, 'add_database()-main-single:', 'mysql exception '
                                                  'inserting new single budget main transaction record:',
                                                  str(excp)])
                    return
            else:  # Checks
                query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_date,'
                         'comments,clear_date) values ("'
                         + new_transaction[g.tID] + '","'
                         + str(new_transaction[g.tCkn]) + '","'
                         + '{0:.2f}'.format((new_transaction[g.tAmount]
                                             if new_transaction[g.tAmount] else 0.0)) + '",'
                         + ('"' + new_transaction[g.tDate].strftime('%Y-%m-%d') + '"'
                            if new_transaction[g.tDate] else 'NULL') + ',"'
                         + new_transaction[g.tPayee] + '","'
                         + new_transaction[g.tBudarr][0][0] + '","'
                         + '{0:.2f}'.format((new_transaction[g.tBudarr][0][1]
                                             if new_transaction[g.tBudarr][0][1] else 0.0)) + '",'
                         + ('"' + new_transaction[g.tBudarr][0][2].strftime('%Y-%m-%d') + '"'
                            if new_transaction[g.tBudarr][0][2] else 'NULL') + ',"'
                         + new_transaction[g.tComment] + '",'
                         + ('"' + new_transaction[g.tClearDate].strftime('%Y-%m-%d') + '"'
                            if new_transaction[g.tClearDate] else 'NULL') + ');')
                try:
                    self.bud_db.execute_query(query)
                except pymysql.Error as excp:
                    WindowUtils.popup_message_ok([query, 'add_database()-checks-single:',
                                                  'mysql exception inserting new single budget checks '
                                                  'transaction record:', str(excp)])
                    return

    def update_database(self, is_main, old_transaction, new_transaction):
        """Update existing record in the database.

        :param bool is_main: whether the database table to update is main or checks
        :param dict old_transaction: database entry to delete
        :param dict new_transaction: database entry to add
        """
        # First, find all the database records that match the tran_ID/tnum base
        # (optional multi-budget ending stripped off)
        # Transaction ID for multi budget database records always ends in
        # '...-<one or more digits>'
        # If the number of database records equals the number of budget entries
        # in the old transaction record, then go to the next step.
        old_tid = old_transaction[g.tID]
        temp = old_tid.split('-')
        old_is_multi = len(temp) > 1 and temp[-1].isdigit()
        if old_is_multi:
            idx = old_tid.rfind('-')
            old_tid_base = old_tid[:idx]
        else:
            old_tid_base = old_tid

        query = ""
        # Make sure transaction ID matches with multiple or single budget entries
        if not old_is_multi and len(old_transaction[g.tBudarr]) > 1:
            WindowUtils.popup_message_ok('update_database(): This transaction ID implies single budget, '
                                         'but the transaction record has more than 1 entry.')
            return
        elif old_is_multi and len(old_transaction[g.tBudarr]) < 2:
            WindowUtils.popup_message_ok('update_database(): This transaction ID implies multi budget, '
                                         'but the transaction record has less than 2 entries.')
            return

        try:
            query = ('select * from ' + ('main' if is_main else 'checks') + ' where ' +
                     ('tran_ID' if is_main else 'tnum') + ' like "' + old_tid_base + '%";')
            db_cursor = self.bud_db.execute_query(query)
        except pymysql.Error as excp:
            WindowUtils.popup_message_ok('update_database(): mysql exception counting old transaction '
                                         'database records: ' + str(excp))
            return

        num_rows = db_cursor.rowcount

        # Make sure multiple budget entries have the same number in the transaction and database
        if old_is_multi and not num_rows == len(old_transaction[g.tBudarr]):
            WindowUtils.popup_message_ok('update_database(): This transaction has multiple budget '
                                         'entries, but the ' + ('main' if is_main else 'checks') +
                                         ' database and transaction don\'t agree how many')
            return

        # Make sure transaction IDs that imply single budget only have 1 record in the database
        elif not old_is_multi and num_rows != 1:
            WindowUtils.popup_message_ok('update_database(): This transaction has only one budget entry,'
                                         ' but the ' + ('main' if is_main else 'checks') +
                                         ' database has ' + str(num_rows) + ' rows instead. Query="' +
                                         query + '"')
            return

        #
        # Second, now that number of database entries agrees with old transaction, delete the database
        # record(s) for the old transaction
        #
        try:
            self.bud_db.execute_query('delete from ' + ('main' if is_main else 'checks') + ' where '
                                      + ('tran_ID' if is_main else 'tnum')
                                      + ' like "' + old_tid_base + '%";')
        except pymysql.Error as excp:
            WindowUtils.popup_message_ok(['update_database():',
                                          'mysql exception deleting old transaction database record(s):',
                                          str(excp)])
            return

        #
        # Third, insert the records from the new_transaction into the database Be careful: the new
        # transaction may not be the same multi as the old transaction. The number of budget entries in
        # the new transaction is independent of the old transaction.

        # We can'temp change the base transaction ID, so the old one is carried through to the new one.
        new_tid = new_transaction[g.tID]

        # The new one may or may not be multi just like the old one may or may not be multi. It needs to
        # represent the new transaction, not the old one.
        temp = new_tid.split('-')
        if len(temp) > 1 and temp[-1].isdigit():
            idx = new_tid.rfind('-')
            new_tid_base = new_tid[:idx]
        else:
            new_tid_base = new_tid
        new_is_multi = len(new_transaction[g.tBudarr]) > 1
        if new_is_multi:
            if is_main:
                i = 0
                for bud_array in new_transaction[g.tBudarr]:
                    query = ('insert into main '
                             '(tran_date, tran_ID, tran_desc, tran_checknum, tran_type, tran_amount, '
                             'bud_category, bud_amount, bud_date, comment) '
                             'values ("'
                             + new_transaction[g.tDate].strftime('%Y-%m-%d') + '","'
                             + old_tid_base + '-' + str(i) + '","'
                             + new_transaction[g.tPayee] + '","'
                             + str(new_transaction[g.tCkn]) + '","'
                             + new_transaction[g.tType] + '","'
                             + '{0:.2f}'.format(new_transaction[g.tAmount]) + '","'
                             + bud_array[0] + '","'
                             + '{0:.2f}'.format(bud_array[1]) + '","'
                             + bud_array[2].strftime('%Y-%m-%d') + '","'
                             + new_transaction[g.tComment] + '");')
                    try:
                        self.bud_db.execute_query(query)
                    except pymysql.Error as excp:
                        WindowUtils.popup_message_ok([query,
                                                      'update_database()-main-multi: mysql exception '
                                                      'inserting new multibudget main transaction '
                                                      'records:', str(excp)])
                        return
                    i += 1
            else:
                i = 0
                for bud_array in new_transaction[g.tBudarr]:
                    query = ('insert into checks (tnum, tchecknum, tamt, tdate, tpayee, bud_cat, bud_amt'
                             ', bud_date, comments, clear_date) values ("'
                             + old_tid_base + '-' + str(i) + '","'
                             + str(new_transaction[g.tCkn]) + '","'
                             + '{0:.2f}'.format((new_transaction[g.tAmount]
                                                 if new_transaction[g.tAmount] else 0.0)) + '",'
                             + ('"' + new_transaction[g.tDate].strftime('%Y-%m-%d') + '"'
                                if new_transaction[g.tDate] else 'NULL') + ',"'
                             + new_transaction[g.tPayee] + '","'
                             + bud_array[0] + '","'
                             + '{0:.2f}'.format((bud_array[1] if bud_array[1] else 0.0)) + '",'
                             + ('"'+bud_array[2].strftime('%Y-%m-%d')+'"'
                                if bud_array[2] else 'NULL') + ',"'
                             + new_transaction[g.tComment] + '",'
                             + ('"' + new_transaction[g.tClearDate].strftime('%Y-%m-%d') + '"'
                                if new_transaction[g.tClearDate] else 'NULL') + ');')
                    try:
                        self.bud_db.execute_query(query)
                    except pymysql.Error as excp:
                        WindowUtils.popup_message_ok([query,
                                                      'update_database()-checks-multi: mysql exception '
                                                      'inserting new multibudget checks transaction '
                                                      'records:', str(excp)])
                        return
                    i += 1
        else:  # single budget items
            if is_main:
                query = ('insert into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran_amo'
                         'unt,bud_category,bud_amount,bud_date,comment) values ("'
                         + new_transaction[g.tDate].strftime('%Y-%m-%d') + '","'
                         + new_transaction[g.tID] + '","'
                         + new_transaction[g.tPayee] + '","'
                         + str(new_transaction[g.tCkn]) + '","'
                         + new_transaction[g.tType] + '","'
                         + '{0:.2f}'.format(new_transaction[g.tAmount]) + '","'
                         + new_transaction[g.tBudarr][0][0] + '","'
                         + '{0:.2f}'.format(new_transaction[g.tBudarr][0][1]) + '","'
                         + new_transaction[g.tBudarr][0][2].strftime('%Y-%m-%d') + '","'
                         + new_transaction[g.tComment] + '");')
                try:
                    self.bud_db.execute_query(query)
                except pymysql.Error as excp:
                    WindowUtils.popup_message_ok([query,
                                                  'update_database()-main-single: mysql exception '
                                                  'inserting new single budget main transaction record:',
                                                  str(excp)])
                    return
            else:  # checks
                query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_date,'
                         'comments,clear_date) values ("'
                         + new_transaction[g.tID] + '","'
                         + str(new_transaction[g.tCkn]) + '","'
                         + '{0:.2f}'.format((new_transaction[g.tAmount]
                                             if new_transaction[g.tAmount] else 0.0)) + '",'
                         + ('"' + new_transaction[g.tDate].strftime('%Y-%m-%d') + '"'
                            if new_transaction[g.tDate] else 'NULL') + ',"'
                         + new_transaction[g.tPayee] + '","'
                         + new_transaction[g.tBudarr][0][0] + '","'
                         + '{0:.2f}'.format((new_transaction[g.tBudarr][0][1]
                                             if new_transaction[g.tBudarr][0][1] else 0.0)) + '",'
                         + ('"' + new_transaction[g.tBudarr][0][2].strftime('%Y-%m-%d') + '"'
                            if new_transaction[g.tBudarr][0][2] else 'NULL') + ',"'
                         + new_transaction[g.tComment] + '",'
                         + ('"' + new_transaction[g.tClearDate].strftime('%Y-%m-%d') + '"'
                            if new_transaction[g.tClearDate] else 'NULL') + ');')
                try:
                    self.bud_db.execute_query(query)
                except pymysql.Error as excp:
                    WindowUtils.popup_message_ok([query,
                                                  'update_database()-main-single: mysql exception '
                                                  'inserting new single budget checks transaction '
                                                  'record:', str(excp)])
                    return
