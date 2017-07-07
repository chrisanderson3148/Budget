import MySQLdb
import curses
from Window import MyWindow
import WindowUtils
import datetime
from mysettings import g

'''
Subclass of MyWindow
Defined in this file because it is very specific to this script
'''
class EditWindow(MyWindow):

    def __init__(self, screen, budDB, n, fgcolor, bgcolor, sWindow, log):
        self.budDB = budDB
        self.n = n
        self.fgcolor = fgcolor
        self.bgcolor = bgcolor
        curses.init_pair(n, fgcolor, bgcolor)
        super(EditWindow, self).__init__(screen, 'edit', sWindow, log)

    def draw_border(self):
        self.win.box(self.vch, self.hch)
        self.win.addstr(0, (self.width-len(self.title))/2, self.title, curses.A_STANDOUT)
        self.win.addstr(0, self.width-10, 'Page %d/%d' % (self.currpage, self.pages), curses.A_STANDOUT)
        self.win.addstr(0, 2, 'Pos: %d,%d'%(self.currx, self.curry), curses.A_STANDOUT)
        self.win.move(self.curry, self.currx)
        self.win.refresh()
        self.log.write('draw_border[EditWindow] window '
                       '(title='+self.title+')\n')

    def draw_win(self, isMain, tdate, tdesc, ttype, tamount, budarr, tcomment, extrafield):
        self.win.clear()
        self.win.addstr(1, 1, 'Transaction date:')
        self.win.addstr(1, 20, (tdate.strftime('%m/%d/%Y') if tdate is not None else '---'))
        if not isMain:
            self.win.addstr(1, 35, 'Cleared date:')
            self.win.addstr(1, 49,
                            (extrafield.strftime('%m/%d/%Y') if extrafield is not None else '---'))
        self.win.addstr(2, 1, 'Description:')
        # Adding this field as editable
        self.win.addstr(2, 15, tdesc[:60], curses.A_REVERSE)
        self.win.addstr(3, 1, ('Type:' if isMain else 'Chk#:'))
        self.win.addstr(3, 7, ttype)
        self.win.addstr(3, 15, 'Amount:')
        self.win.addstr(3, 23, '$%10.2f'%(tamount if tamount else 0))
        self.win.addstr(4, 1, 'Comments:')
        self.win.addstr(4, 11, tcomment, curses.A_REVERSE)
        self.win.addstr(6, 1, 'Budget items = '+str(len(budarr)))
        self.win.addstr(7, 1, 'Budget category')
        self.win.addstr(7, 18, 'Budget amount')
        self.win.addstr(7, 35, 'Budget date')
        rownum = 8
        self.balance = float(tamount if tamount else 0)
        for budlist in budarr:
            self.win.addstr(rownum, 1, budlist[0], curses.A_REVERSE)
            self.win.addstr(rownum, 18, '%10.2f'%budlist[1], curses.A_REVERSE)
            self.win.addstr(rownum, 35,
                            (budlist[2].strftime('%m/%d/%Y') if budlist[2] is not None else '---'),
                            curses.A_REVERSE)
            rownum += 1
            self.balance -= float(budlist[1])
        self.win.addstr(6, 20, 'Balance: '+'%5.2f'%self.balance)
        self.draw_border()
        self.read_content_lines()
        self.log.write('draw_win[EditWindow] window (title='+self.title+')\n')

    def refresh(self, isMain, entry):
        if isMain:
            self.draw_win(True, entry[g.tDate], entry[g.tPayee], entry[g.tType], entry[g.tAmount],
                          entry[g.tBudarr], entry[g.tComment], '')
        else:
            self.draw_win(False, entry[g.tDate], entry[g.tPayee], str(entry[g.tClearDate]),
                          entry[g.tAmount], entry[g.tBudarr], entry[g.tComment], entry[g.tClearDate])

    def refresh_both(self, isMain, entry):
        if isMain: # main table transactions
            self.draw_win(True,
                          entry[g.tDate],    # transaction date
                          entry[g.tPayee],   # transaction payee
                          entry[g.tType],    # transaction type
                          entry[g.tAmount],  # transaction amount
                          entry[g.tBudarr],  # transaction budget list of lists
                          entry[g.tComment], # transaction comment, if any
                          '')                # extra field (not used by main transactions)
        else: # checks table transactions
            self.draw_win(False,
                          entry[g.tDate],      # transaction date
                          entry[g.tPayee],     # transaction payee
                          str(entry[g.tCkn]),  # transaction check number
                          entry[g.tAmount],    # transaction amount
                          entry[g.tBudarr],    # transaction budget list of lists
                          entry[g.tComment],   # transaction comment, if any
                          entry[g.tClearDate]) # check cleared date (check
                                               # transactions only)

    '''
    With the new combined main/checks transactions, the format of the checks entry is the same as the
    format of the main entry. This has implications in this function and in update_transaction.
    NEW FORMAT
    '''
    def main_event_loop(self, isMain, entry, readonly=False):
        numbudentries = len(entry[g.tBudarr])
        tabarr = list()
        tabarr.append([15, 2, 'desc'])
        tabarr.append([11, 4, 'comments'])
        for i in range(8, 8+numbudentries): # range(first, last+1)
            tabarr.append([1, i, 'category'])
            tabarr.append([18, i, 'amount'])
            tabarr.append([35, i, 'date'])

        # all this call does is copy-by-value the entry to the returned list
        newentry = self.update_transaction(isMain, entry, '', [])
        changes = False
        idx = 0

        #
        # Event Loop
        #
        while True:
            self.win.move(tabarr[idx][1], tabarr[idx][0])
            self.win.refresh()
            self.curry, self.currx = self.win.getyx()
            self.draw_border()

            i = self.s.getch()
            if i == ord('\t'):
                idx = (idx + 1) % len(tabarr)
            #
            # Add a new, empty budget entry
            #
            elif i == ord('a') and not readonly:
                newguy = ['UNKNOWN', 0.00, datetime.datetime.today()]
                #newentry[6 if isMain else 5].append(newguy)
                newentry[g.tBudarr].append(newguy)
                newline = tabarr[-1][1]
                tabarr.append([1, newline+1, 'category'])
                tabarr.append([18, newline+1, 'amount'])
                tabarr.append([35, newline+1, 'date'])
                self.refresh(isMain, newentry)
                changes = True
            #
            # Delete selected budget entry
            #
            elif i == ord('d') and not readonly:
                if tabarr[idx][1] < 8: # MAGIC number
                    WindowUtils.popup_message_ok(self.s, 'You can only delete budget items.',
                                                 self.sWindow, self.log)
                    continue
                #if len(newentry[6 if isMain else 5]) < 2:
                if len(newentry[g.tBudarr]) < 2:
                    WindowUtils.popup_message_ok(self.s, 'You cannot delete the only budget item.',
                                                 self.sWindow, self.log)
                    continue
                row = tabarr[idx][1] - 8
                #del newentry[6 if isMain else 5][row]
                del newentry[g.tBudarr][row]
                del tabarr[-1] # delete last row (3 entries per row)
                del tabarr[-1]
                del tabarr[-1]

                # If we were on the last line that got deleted
                if idx > len(tabarr)-1:
                    idx -= 3 # Move us to the previous line
                self.refresh(isMain, newentry)
                changes = True
            #
            # Change an existing record field
            #
            # edit current field
            elif (i == ord('r') or i == ord('e')) and not readonly:
                curses.echo()
                text = self.win.getstr()
                curses.noecho()

                # replace all " with ' because of the mysql update query will
                # fail on " (it uses " to delimit field values)
                text = text.replace('"', "'")
                newentry = self.update_transaction(isMain, newentry, text, tabarr[idx])
                self.refresh(isMain, newentry)
                changes = True
            #
            # 'quit', saving all changes
            #
            elif i == ord('q'):
                if changes and not readonly:

                    # rounding errors will not produce an exact 0.00000
                    if abs(self.balance) >= 0.005:
                        WindowUtils.popup_message_ok(
                            self.s,
                            ['Balance between transaction amount and sum of budget amounts is not '
                             'equal.', 'The difference is ${0:.2f}'.format(self.balance)],
                            self.sWindow, self.log)
                        continue
                    self.update_database(isMain, entry, newentry)
                break # keep value of 'changes' the same
            #
            # 'exit' without saving any changes
            #
            elif i == ord('x'):
                if changes:
                    answer = WindowUtils.popup_get_yes_no(self.s,
                                                          'There were changes. Exit without saving?',
                                                          self.sWindow, self.log, default='NO')
                    if answer.lower() == 'no':
                        continue
                changes = False
                break

        return changes

    def check_event_loop(self, entry, add):
        numbudentries = len(entry[g.tBudarr])
        tabarr = [[19, 1, 'tdate'], [15, 2, 'tpayee'], [7, 3, 'checknum'], [23, 3, 'tamt'],
                  [11, 4, 'comments']]
        for i in range(8, 8+numbudentries): # range(start, stop+1)
            tabarr.append([1, i, 'category'])
            tabarr.append([18, i, 'amount'])
            tabarr.append([35, i, 'date'])

        # all this call does is copy-by-value the entry (which itself can be an
        # empty transaction) to the returned list
        newentry = self.update_transaction(False, entry, '', [])
        changes = False
        idx = 0
        while True:
            self.win.move(tabarr[idx][1], tabarr[idx][0])
            self.win.refresh()
            self.curry, self.currx = self.win.getyx()
            self.draw_border()
            i = self.s.getch()
            if i == ord('\t'):
                idx = (idx + 1) % len(tabarr)
            if i == ord('r') or i == ord('e'):
                curses.echo()
                text = self.win.getstr()
                curses.noecho()

                # replace all " with ' because of the mysql update query will
                # fail on " (it uses " to delimit field values)
                text = text.replace('"', "'")

                # Verify that the value of checknum is not already in the
                # database and is an integer
                if tabarr[idx][2] == 'checknum':
                    dbcur = self.budDB.executeQuery('SELECT * FROM checks WHERE tnum = "' + text + '";')
                    numrows = dbcur.rowcount

                    # If it is in the database, notify and cancel
                    if numrows > 0:
                        WindowUtils.popup_message_ok(self.s,
                                                     'Check number '+text+' is already in the database',
                                                     self.sWindow, self.log)

                        # erase previous entry
                        self.win.addstr(tabarr[idx][1], tabarr[idx][0], '      ')
                        continue
                    try:
                        int(text)
                    except ValueError:
                        WindowUtils.popup_message_ok(self.s,
                                                     'Field "'+tabarr[idx][2]+'" value '+text+' is not a'
                                                     'n integer',
                                                     self.sWindow, self.log)

                        # erase previous entry
                        self.win.addstr(tabarr[idx][1], tabarr[idx][0], '      ')
                        continue

                # Verify that the value of tamt is a float
                elif tabarr[idx][2] == 'tamt' or tabarr[idx][2] == 'amount':
                    try:
                        float(text)
                    except ValueError:
                        WindowUtils.popup_message_ok(self.s,
                                                     'Field "'+tabarr[idx][2]+'" value '+text+' is not a'
                                                     ' float',
                                                     self.sWindow, self.log)

                        # erase previous entry
                        self.win.addstr(tabarr[idx][1], tabarr[idx][0], '             ')
                        continue

                # Verify that the value of tdate or budget date is a date
                # (mm/dd/yyyy)
                elif tabarr[idx][2] == 'tdate' or tabarr[idx][2] == 'date':
                    try:
                        datetime.datetime.strptime(text, '%m/%d/%Y')
                    except ValueError:
                        WindowUtils.popup_message_ok(self.s,
                                                     'Field "'+tabarr[idx][2]+'" value '+text+' is not a'
                                                     ' date (mm/dd/yyyy)',
                                                     self.sWindow, self.log)

                        # erase previous entry
                        self.win.addstr(tabarr[idx][1], tabarr[idx][0], '          ')
                        continue
                newentry = self.update_transaction(False, newentry, text, tabarr[idx])
                self.draw_win(False, newentry[g.tDate], newentry[g.tPayee], str(newentry[g.tCkn]),
                              newentry[g.tAmount], newentry[g.tBudarr], newentry[g.tComment],
                              newentry[g.tClearDate])
                changes = True
                idx = (idx + 1) % len(tabarr)
            if i == ord('q'): # 'quit', saving any changes
                if changes:

                    # rounding errors will not produce an exact 0.00000
                    if abs(self.balance) >= 0.005:
                        WindowUtils.popup_message_ok(self.s,
                                                     ['Balance between transaction amount and sum of bud'
                                                      'get amounts is not equal.',
                                                      'The difference is ${0:.2f}'.format(self.balance)],
                                                     self.sWindow, self.log)
                        continue
                    '''
                    Somehow have to differentiate between an updated check
                    record and a new record to be inserted.
                    '''
                    if not newentry[1] or len(newentry[5]) == 0:
                        WindowUtils.popup_message_ok(self.s, 'One or more required fields are empty.',
                                                     self.sWindow, self.log)
                        continue

                    if add:
                        # if add==True, then the original entry was empty
                        self.addDatabase(False, newentry)
                    else:
                        # if add==False, then the original entry was full
                        self.update_database(False, entry, newentry)
                break # keep value of 'changes' the same
            if i == ord('x'): # 'exit' without saving any changes
                if changes:
                    answer = WindowUtils.popup_get_yes_no(self.s,
                                                          'There were changes. Exit without saving?',
                                                          self.sWindow, self.log, default='NO')
                    if answer.lower() == 'no':
                        continue
                changes = False
                break

        return changes

    '''
    Update transaction with any changes
    fieldarr is a 3-element array as [xpos, ypos, name]
    '''
    def update_transaction(self, isMain, transaction, newvalue, fieldarr):
        import copy

        # copy everything by VALUE not by REFERENCE so changes made here don't
        # ripple back to the original
        newtransaction = copy.deepcopy(transaction)

        # All we wanted to do was make a copy of the incoming transaction
        if len(fieldarr) == 0:
            return newtransaction

        # Set from constants for fieldarr elements
        fieldx = fieldarr[0]
        fieldy = fieldarr[1]
        fieldname = fieldarr[2]
        budgetentry = fieldy - 8 # MAGIC NUMBER

        # Verify budget entry
        if budgetentry < 0 and (fieldname == 'category' or fieldname == 'amount' or fieldname == 'date'):
            WindowUtils.popup_message_ok(self.s,
                                         'fieldname='+fieldname+', but fieldy < 8: '+str(fieldy),
                                         self.sWindow, self.log)
            return newtransaction

        bud_array = newtransaction[g.tBudarr]

        # Overwrite the field that changed
        updatequery = ''
        if fieldname == 'checknum': # Checks only
            newtransaction[g.tCkn] = newvalue

            # checknum and transaction num are the same
            newtransaction[g.tID] = newvalue
        if fieldname == 'tamt': # Checks only
            try:
                amount = float(newvalue)
                # Check amounts are ALWAYS negative
                amount = -1.0*abs(amount)

                # convert field back to floating point
                newtransaction[g.tAmount] = amount
            except ValueError:
                WindowUtils.popup_message_ok(self.s, '"{}" is not a float!'.format(newvalue),
                                             self.sWindow, self.log)

        if fieldname == 'tdate': # Checks only
            try:
                # convert field back to date object
                newtransaction[g.tDate] = datetime.datetime.strptime(newvalue, '%m/%d/%Y')
            except ValueError:
                WindowUtils.popup_message_ok(self.s, 'Bad date format. Expected format is m/d/yyyy',
                                             self.sWindow, self.log)
                return newtransaction
        if fieldname == 'tpayee': # Checks only
            newtransaction[g.tPayee] = newvalue
        if fieldname == 'comments': # Either main or checks
            newtransaction[g.tComment] = newvalue
        if fieldname == 'desc': # Either main or checks
            newtransaction[g.tPayee] = newvalue

        '''
        This section applies to the budget item(s) in the transaction, either
        main or checks
        '''
        if fieldname == 'category':
            # all budget categories are upper-case
            bud_array[budgetentry][0] = newvalue.upper()
            newtransaction[g.tBudarr] = bud_array
        if fieldname == 'amount':
            # convert field back to floating point
            try:
                bud_array[budgetentry][1] = float(newvalue)
                newtransaction[g.tBudarr] = bud_array
            except ValueError:
                WindowUtils.popup_message_ok(self.s, '"{}" is not a float!'.format(newvalue),
                                             self.sWindow, self.log)

        if fieldname == 'date':
            try:
                # convert field back to date object
                bud_array[budgetentry][2] = datetime.datetime.strptime(newvalue, '%m/%d/%Y')
            except ValueError:
                WindowUtils.popup_message_ok(self.s,
                                             'Bad date format. Expected format is m/d/yyyy (' +newvalue
                                             +')',
                                             self.sWindow, self.log)
                return newtransaction
            newtransaction[g.tBudarr] = bud_array

        return newtransaction # return the new, changed transaction record

    '''
    This function is to add new records to the database
    '''
    def add_database(self, isMain, newtransaction):
        #
        # First, find all the database records that match the tran_ID/tnum base
        # of the new transaction to add, and make sure there are none.
        #
        tid = newtransaction[g.tID]
        try:
            dbcur = self.budDB.executeQuery('select * from '+('main' if isMain else 'checks')
                                            +' where '+('tran_ID' if isMain else 'tnum')
                                            +' like "'+tid+'%";')
        except MySQLdb.Error, e:
            WindowUtils.popup_message_ok(self.s,
                                         'mysql exception counting transaction database records with tra'
                                         'nsaction id '+tid+': '+str(e),
                                         self.sWindow, self.log)
            return
        numrows = dbcur.rowcount
        if numrows > 0:
            WindowUtils.popup_message_ok(self.s,
                                         'There are already '+str(numrows)+' rows in the database for tr'
                                         'ansaction id '+tid+' that we want to add.',
                                         self.sWindow, self.log)
            return

        #
        # Second, insert the records from the newtransaction into the database
        #
        newmulti = len(newtransaction[g.tBudarr]) > 1
        if newmulti:
            if isMain:
                i = 0
                for budarr in newtransaction[g.tBudarr]:
                    query = ('insert into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran'
                             '_amount,bud_category,bud_amount,bud_date,comment) '
                             'values ("'+newtransaction[g.tDate].strftime('%Y-%m-%d')+'","'
                             +tid+'-'+str(i)+'","'+newtransaction[g.tPayee]+'","'
                             +str(newtransaction[g.tCkn])+'","'
                             +newtransaction[g.tType]+'","'+'{0:.2f}'.format(newtransaction[g.tAmount])
                             +'","'+budarr[0]+'","'+'{0:.2f}'.format(budarr[1])+'","'
                             +budarr[2].strftime('%Y-%m-%d')+'","'+newtransaction[g.tComment]+'");')
                    try:
                        self.budDB.executeQuery(query)
                    except MySQLdb.Error, e:
                        WindowUtils.popup_message_ok(self.s,
                                                     [query, 'addDatabase()-main-multi:', 'mysql excepti'
                                                      'on inserting new multibudget main transaction rec'
                                                      'ords:', str(e)],
                                                     self.sWindow, self.log)
                        return
                    i += 1
            else: # Checks
                i = 0
                for budarr in newtransaction[g.tBudarr]:
                    query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_d'
                             'ate,comments,clear_date) values ("'+tid+'-'+str(i)+'","'
                             +str(newtransaction[g.tCkn])+'","'
                             +'{0:.2f}'.format((newtransaction[g.tAmount]
                                                if newtransaction[g.tAmount] else 0.0))
                             +'",'+('"'+newtransaction[g.tDate].strftime('%Y-%m-%d')+'"'
                                    if newtransaction[g.tDate] else 'NULL')
                             +',"'+newtransaction[g.tPayee]+'","'+budarr[0]+'","'
                             +'{0:.2f}'.format((budarr[1] if budarr[1] else 0.0))+'",'
                             +('"'+budarr[2].strftime('%Y-%m-%d')+'"' if budarr[2] else 'NULL')
                             +',"'+budarr[2].strftime('%Y-%m-%d')+'","'+newtransaction[g.tComment]+'",'
                             +('"'+newtransaction[g.tClearDate].strftime('%Y-%m-%d')+'"'
                               if newtransaction[g.tClearDate] else 'NULL')+');')
                    try:
                        self.budDB.executeQuery(query)
                    except MySQLdb.Error, e:
                        WindowUtils.popup_message_ok(self.s,
                                                     [query, 'addDatabase()-checks-multi:', 'mysql excep'
                                                      'tion inserting new multibudget checks transaction'
                                                      ' records:', str(e)],
                                                     self.sWindow, self.log)
                        return
                    i += 1
        else: # single budget items
            if isMain:
                query = ('insert into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran_amo'
                         'unt,bud_category,bud_amount,bud_date,comment) values ('
                         '"'+newtransaction[g.tDate].strftime('%Y-%m-%d')+'",'
                         '"'+newtransaction[g.tID]+'",'
                         '"'+newtransaction[g.tPayee]+'",'
                         '"'+str(newtransaction[g.tCkn])+'",'
                         '"'+newtransaction[g.tType]+'",'
                         '"'+'{0:.2f}'.format(newtransaction[g.tAmount])+'",'
                         '"'+newtransaction[g.tBudarr][0][0]+'",'
                         '"'+'{0:.2f}'.format(newtransaction[g.tBudarr][0][1])+'",'
                         '"'+newtransaction[g.tBudarr][0][2].strftime('%Y-%m-%d')+'",'
                         '"'+newtransaction[g.tComment]+'");'
                        )
                try:
                    self.budDB.executeQuery(query)
                except MySQLdb.Error, e:
                    WindowUtils.popup_message_ok(self.s,
                                                 [query, 'addDatabase()-main-single:', 'mysql exception '
                                                  'inserting new single budget main transaction record:',
                                                  str(e)],
                                                 self.sWindow, self.log)
                    return
            else: # Checks
                query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_date,'
                         'comments,clear_date) values ("'
                         +newtransaction[g.tID]+'","'
                         +str(newtransaction[g.tCkn])+'","'
                         +'{0:.2f}'.format((newtransaction[g.tAmount]
                                            if newtransaction[g.tAmount] else 0.0))+'",'
                         +('"'+newtransaction[g.tDate].strftime('%Y-%m-%d')+'"'
                           if newtransaction[g.tDate] else 'NULL')+',"'
                         +newtransaction[g.tPayee]+'","'
                         +newtransaction[g.tBudarr][0][0]+'","'
                         +'{0:.2f}'.format((newtransaction[g.tBudarr][0][1]
                                            if newtransaction[g.tBudarr][0][1] else 0.0))+'",'
                         +('"'+newtransaction[g.tBudarr][0][2].strftime('%Y-%m-%d')+'"'
                           if newtransaction[g.tBudarr][0][2] else 'NULL')+',"'
                         +newtransaction[g.tComment]+'",'
                         +('"'+newtransaction[g.tClearDate].strftime('%Y-%m-%d')+'"'
                           if newtransaction[g.tClearDate] else 'NULL')+');'
                        )
                try:
                    self.budDB.executeQuery(query)
                except MySQLdb.Error, e:
                    WindowUtils.popup_message_ok(self.s,
                                                 [query, 'addDatabase()-checks-single:',
                                                  'mysql exception inserting new single budget checks tr'
                                                  'ansaction record:',
                                                  str(e)],
                                                 self.sWindow, self.log)
                    return

    '''
    This function is to change existing records in the database
    '''
    def update_database(self, isMain, oldtransaction, newtransaction):
        # First, find all the database records that match the tran_ID/tnum base
        # (optional multi-budget ending stripped off)
        # Transaction ID for multi budget database records always ends in
        # '...-<one or more digits>'
        # If the number of database records equals the number of budget entries
        # in the old transaction record, then go to the next step.
        oldtid = oldtransaction[g.tID]
        t = oldtid.split('-')
        oldmulti = len(t) > 1 and t[-1].isdigit()
        if oldmulti:
            idx = oldtid.rfind('-')
            oldtidbase = oldtid[:idx]
        else:
            oldtidbase = oldtid

        # Make sure transaction ID matches with multiple or single budget
        # entries
        if not oldmulti and len(oldtransaction[g.tBudarr]) > 1:
            WindowUtils.popup_message_ok(self.s,
                                         'This transaction ID implies single budget, but the transaction'
                                         ' record has more than 1 entry.',
                                         self.sWindow, self.log)
            return
        elif oldmulti and len(oldtransaction[g.tBudarr]) < 2:
            WindowUtils.popup_message_ok(self.s,
                                         'This transaction ID implies multi budget, but the transaction '
                                         'record has less than 2 entries.',
                                         self.sWindow, self.log)
            return

        try:
            dbcur = self.budDB.executeQuery('select * from '+('main' if isMain else 'checks')+' where '
                                            +('tran_ID' if isMain else 'tnum')
                                            +' like "'+oldtidbase+'%";')
        except MySQLdb.Error, e:
            WindowUtils.popup_message_ok(self.s,
                                         'mysql exception counting old transaction database records: '
                                         +str(e),
                                         self.sWindow, self.log)
            return
        numrows = dbcur.rowcount

        # Make sure multiple budget entries have the same number in the
        # transaction and database
        if oldmulti and not numrows == len(oldtransaction[g.tBudarr]):
            WindowUtils.popup_message_ok(self.s,
                                         'This transaction has multiple budget entries, but the database'
                                         ' and transaction don\'t agree how many',
                                         self.sWindow, self.log)
            return
        # Make sure transaction IDs that imply single budget only have 1 record
        # in the database
        elif not oldmulti and numrows != 1:
            WindowUtils.popup_message_ok(self.s,
                                         'This transaction has only one budget entry, but the database h'
                                         'as '+str(numrows)+' rows instead.',
                                         self.sWindow, self.log)
            return

        #
        # Second, delete the database record(s) for the old transaction
        #
        try:
            self.budDB.executeQuery('delete from '+('main' if isMain else 'checks')+' where '
                                    +('tran_ID' if isMain else 'tnum')+' like "'+oldtidbase+'%";')
        except MySQLdb.Error, e:
            WindowUtils.popup_message_ok(self.s,
                                         ['update_database():',
                                          'mysql exception deleting old transaction database record(s):',
                                          str(e)],
                                         self.sWindow, self.log)
            return

        #
        # Third, insert the records from the newtransaction into the database
        # Be careful: the new transaction may not be the same multi as the old
        # transaction.
        # The new transaction starts fresh relating to multi or not.
        #

        # we can't change the transaction ID, so the old one is carried through
        # to the new one.
        newtid = newtransaction[g.tID]

        # The new one may or may not be multi just like the old one may or may
        # not be multi. It needs to represent the new transaction, not the old
        # one.
        t = newtid.split('-')
        if len(t) > 1 and t[-1].isdigit():
            idx = newtid.rfind('-')
            newtidbase = newtid[:idx]
        else:
            newtidbase = newtid
        newmulti = len(newtransaction[g.tBudarr]) > 1
        if newmulti:
            if isMain:
                i = 0
                for budarr in newtransaction[g.tBudarr]:
                    query = ('insert into main '
                             '(tran_date, tran_ID, tran_desc, tran_checknum, tran_type, tran_amount, '
                             'bud_category, bud_amount, bud_date, comment) '
                             'values ("'
                             +newtransaction[g.tDate].strftime('%Y-%m-%d')+'","'
                             +oldtidbase+'-'+str(i)+'","'
                             +newtransaction[g.tPayee]+'","'
                             +str(newtransaction[g.tCkn])+'","'
                             +newtransaction[g.tType]+'","'
                             +'{0:.2f}'.format(newtransaction[g.tAmount])+'","'
                             +budarr[0]+'","'
                             +'{0:.2f}'.format(budarr[1])+'","'
                             +budarr[2].strftime('%Y-%m-%d')+'","'
                             +newtransaction[g.tComment]+'");')
                    try:
                        self.budDB.executeQuery(query)
                    except MySQLdb.Error, e:
                        WindowUtils.popup_message_ok(self.s,
                                                     [query,
                                                      'update_database()-main-multi: mysql exception ins'
                                                      'erting new multibudget main transaction records:',
                                                      str(e)],
                                                     self.sWindow, self.log)
                        return
                    i += 1
            else:
                i = 0
                for budarr in newtransaction[g.tBudarr]:
                    query = ('insert into checks (tnum, tchecknum, tamt, tdate, tpayee, bud_cat, bud_amt'
                             ', bud_date, comments, clear_date) values ("'
                             +oldtidbase+'-'+str(i)+'","'
                             +str(newtransaction[g.tCkn])+'","'
                             +'{0:.2f}'.format((newtransaction[g.tAmount]
                                                if newtransaction[g.tAmount] else 0.0))+'",'
                             +('"'+newtransaction[g.tDate].strftime('%Y-%m-%d')+'"'
                               if newtransaction[g.tDate] else 'NULL')+',"'
                             +newtransaction[g.tPayee]+'","'
                             +budarr[0]+'","'
                             +'{0:.2f}'.format((budarr[1] if budarr[1] else 0.0))+'",'
                             +('"'+budarr[2].strftime('%Y-%m-%d')+'"' if budarr[2] else 'NULL')+',"'
                             +newtransaction[g.tComment]+'",'
                             +('"'+newtransaction[g.tClearDate].strftime('%Y-%m-%d')+'"'
                               if newtransaction[g.tClearDate] else 'NULL')+');')
                    try:
                        self.budDB.executeQuery(query)
                    except MySQLdb.Error, e:
                        WindowUtils.popup_message_ok(self.s,
                                                     [query,
                                                      'update_database()-checks-multi: mysql exception i'
                                                      'nserting new multibudget checks transaction recor'
                                                      'ds:',
                                                      str(e)],
                                                     self.sWindow, self.log)
                        return
                    i += 1
        else: # single budget items
            if isMain:
                query = ('insert into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran_amo'
                         'unt,bud_category,bud_amount,bud_date,comment) values ("'
                         +newtransaction[g.tDate].strftime('%Y-%m-%d')+'","'
                         +newtransaction[g.tID]+'","'
                         +newtransaction[g.tPayee]+'","'
                         +str(newtransaction[g.tCkn])+'","'
                         +newtransaction[g.tType]+'","'
                         +'{0:.2f}'.format(newtransaction[g.tAmount])+'","'
                         +newtransaction[g.tBudarr][0][0]+'","'
                         +'{0:.2f}'.format(newtransaction[g.tBudarr][0][1])+'","'
                         +newtransaction[g.tBudarr][0][2].strftime('%Y-%m-%d')+'","'
                         +newtransaction[g.tComment]+'");'
                        )
                try:
                    self.budDB.executeQuery(query)
                except MySQLdb.Error, e:
                    WindowUtils.popup_message_ok(self.s,
                                                 [query,
                                                  'update_database()-main-single: mysql exception insert'
                                                  'ing new single budget main transaction record:',
                                                  str(e)],
                                                 self.sWindow, self.log)
                    return
            else:
                query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_date,'
                         'comments,clear_date) values ("'
                         +newtransaction[g.tID]+'","'
                         +str(newtransaction[g.tCkn])+'","'
                         +'{0:.2f}'.format((newtransaction[g.tAmount]
                                            if newtransaction[g.tAmount] else 0.0))+'",'
                         +('"'+newtransaction[g.tDate].strftime('%Y-%m-%d')+'"'
                           if newtransaction[g.tDate] else 'NULL')+',"'
                         +newtransaction[g.tPayee]+'","'
                         +newtransaction[g.tBudarr][0][0]+'","'
                         +'{0:.2f}'.format((newtransaction[g.tBudarr][0][1]
                                            if newtransaction[g.tBudarr][0][1] else 0.0))+'",'
                         +('"'+newtransaction[g.tBudarr][0][2].strftime('%Y-%m-%d')+'"'
                           if newtransaction[g.tBudarr][0][2] else 'NULL')+',"'
                         +newtransaction[g.tComment]+'",'
                         +('"'+newtransaction[g.tClearDate].strftime('%Y-%m-%d')+'"'
                           if newtransaction[g.tClearDate] else 'NULL')+');'
                        )
                try:
                    self.budDB.executeQuery(query)
                except MySQLdb.Error, e:
                    WindowUtils.popup_message_ok(self.s,
                                                 [query,
                                                  'update_database()-main-single: mysql exception insert'
                                                  'ing new single budget checks transaction record:',
                                                  str(e)],
                                                 self.sWindow, self.log)
                    return


