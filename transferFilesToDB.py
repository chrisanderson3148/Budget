#!/usr/bin/python

import os, sys
import re
import datetime
import glob
from os import path
from warnings import filterwarnings
import collections
import traceback
import pprint
import hashlib
import MySQLdb as Database
from transferPayee import TransferPayee

filterwarnings('ignore', category=Database.Warning)

# Formats of output monthly files by source for one-time transfer to database.
#  Credit Union -- header line and 11 double-quoted, comma-separated fields
#  "Transaction_Date","Transaction_ID","TranDesc","ExtDesc","Description","Fee","Amount","Other_Charges","Balance","Post_Date","Check_Number"
#  "7/1/2015 7:50:12 AM","ID8265","ACH Debit","MGMT SPECIALISTS  - ONLINE PMT","ACH Debit MGMT SPECIALISTS  - ONLINE PMT","","-72","","9243.05","7/1/2015",""
#  American Express -- no header line, 5 fields, some double-quoted, all comma-separated.
     #07/02/2015,"Reference: 320151840289924743",32.52,"TJ MAXX #803 00000088009266299","080305055978009266299"
#  Discover -- no header line, 9 fields, none double-quoted, all comma-separated.
     #2015,07,07,2015,07,07,MT RUSHMORE KOA/PALMER HILL CITY SD00797R,-62.24,Services,TRAVEL
#  Barclay -- no header line, 6 fields, none double-quoted, all comma-separated.
     #2015,02,03,751402150340203151304480108,PAYMENT RECV'D CHECKFREE,566.64

# The common fields from the download files are tran_date, tran_ID, tran_desc,
# tran_amount
# Discover does not have a transaction ID. Historically it's been created as a
#   concatenation of all the field values together.
# The main database table will also include 3 additional fields: bud_category,
#   bud_amount, bud_date
# Normally each record when imported will copy tran_amount to bud_amount, and
#   tran_date to bud_date. The bud_cat field will be filled in by a lookup to
#   the payee table, or if it is a check, from the check table. The tran_desc
#   field will be matched with a known budget category from the payee table or
#   from the check table. If a result is not found in the payee table, then
#   "UNKNOWN" will be entered for bud_category.
# Occasionally there are extra fields in the monthly files, after the default
#   fields. They are for budget override purposes. They can override the budget
#   category, budget date, and/or budget amount. If it overrides the amount,
#   then multiple records with the same tran_date/tran_ID/tran_desc/tran_amount
#   are created, but with different bud_category, bud_date, and bud_amount.
#   These records are connected together by the tran_ID. If a change to the
#   budget date/category/amount is made to any of them, the old set is
#   deleted, and a new set with the changed data is created to replace it.

class TransferMonthlyFilesToDB(object):

    def __init__(self, cursor):
        self.cur = cursor
        # Initialize payee table
        payee = TransferPayee()
        self.payeeDict = payee.readPayeeFile('payee')
        self.pp = pprint.PrettyPrinter(indent=4)
        self.pp.pprint(self.payeeDict)
        self.unexpectedheader = []
        self.totalfiles = 0
        self.filesprocessed = 0
        self.inserted = 0

    def Results(self):
        return self.totalfiles, self.filesprocessed, self.inserted, \
                self.unexpectedheader

    def clearCommasInQuotes(self, repl_char, line):
        start = 0
        while line.find('"', start) != -1:
            idx1 = line.find('"', start) # index of opening quote
            if idx1 == -1: break
            idx2 = line.find('"', idx1+1) # index of closing quote
            if idx2 == -1: # Didn't find a closing quote? Barf
                print('Improperly formed line: opening " but no closing " in li'
                      'ne\n{}'.format(line))
                sys.exit(1)

            # replace all found commas with repl_char within the opening and
            # closing quotes
            while True:
                commaidx = line.find(',', idx1, idx2)
                if commaidx >= 0: # replace found comma with replacement char
                    line = line[:commaidx] + repl_char + line[commaidx+1:]
                else: # found all commas (or there were none)
                    break

            # move after closing quote to begin another search for an opening
            # quote
            start = idx2 + 1
        # now line is clear of confusing commas
        line = line.translate(None, '"') # remove all double-quotes
        return line

    def pretty(self, d, indent=0):
        for key, value in d.iteritems():
            # if indent == 0: print '\n'
            print '  ' * indent + str(key)
            if isinstance(value, dict):
                self.pretty(value, indent+1)
            else:
                print '  ' * (indent+1) + str(value)

    def lookupCUCheckCat(self, checknum, amount, trandate):
        buddict = {}
        payee = 'Unknown'
        self.cur.execute('SELECT tnum,tpayee,bud_cat,bud_amt,bud_date FROM chec'
                         'ks WHERE tchecknum = "'+checknum+'" order by tnum;')
        if self.cur.rowcount > 0:
            for row in self.cur:
                # print checknum, row
                if len(row[0].split('-')) > 1:
                    key = int(row[0].split('-')[1])
                else:
                    key = 0
                payee = row[1]
                budcat = row[2] if row[2] else 'UNKNOWN'
                budamt = str(row[3]) \
                        if not row[3] is None and row[3] > 0.0 else amount
                buddat = row[4].strftime('%m/%d/%Y') \
                        if not row[4] is None else trandate
                buddict[key] = [budcat, budamt, buddat]
        else:
            print 'No matching check '+checknum+' found in checks database'
            buddict[0] = ['UNKNOWN', amount, trandate]
        return payee, buddict

    def lookupPayeeCat(self, payee, buddate):
        # format examples: cat
        #                  cat1,date1;cat2,date2;...;catN
        # The assumption is that each succeeding date is later than the
        # preceding ones and that the last category applies to all later dates

        bud_date = datetime.datetime.strptime(buddate, "%m/%d/%Y").date()

        #
        # This handles the standard, hard-coded payee-to-budget-category
        # transactions
        if 'DISCOVER CARD' in payee or \
                'DISCOVER DC PYMNTS' in payee or \
                'DIRECT PAY FULL BALANCE' in payee or \
                'DIRECTPAY FULL BALANCE' in payee:
            return 'IGNORE'
        if 'AMERICAN EXPRESS' in payee or \
                'BARCLAYS BANK' in payee:
            return 'IGNORE'
        if 'PAYMENT RECEIVED' in payee or \
                'PAYMENT - THANK YOU' in payee or \
                "PAYMENT RECV'D" in payee or \
                'ONLINE PAYMENT THANK YOU' in payee or \
                'PAYMENT THANK YOU' in payee:
            return 'IGNORE'
        if 'Electronic Payment' in payee:
            return 'IGNORE'
        if 'BILL PAYMT' in payee and \
                'COSTCO' in payee:
            return 'IGNORE'
        if 'EDI PAYMTS' in payee and \
                'HEWLETT-PACKARD' in payee:
            return 'PAYROLL'

        if 'Transfer' in payee:
            if '61210600' in payee:
                return 'INSURANCE'
            if '61210601' in payee:
                if bud_date < datetime.datetime.strptime(
                        '08/01/2008', "%m/%d/%Y").date():
                    return 'HOA'
                else:
                    return 'FURNITURE'
            if '61210602' in payee: return 'GIFTS'
            if '61210603' in payee: return 'TRAVEL'
            if '61210604' in payee: return 'CAR MAINT'
            if '61210680' in payee: return 'SAVINGS'
            if '44051209' in payee: return 'MEDICAL'
            return 'TRANSFER'

        #
        # If not a standard, hard-coded budget category, try looking up in the
        # payee database dictionary
        for key in sorted(self.payeeDict):
            matchObj = re.match(self.payeeDict[key][0], payee, re.I)
            if matchObj:
                cats = self.payeeDict[key][1].split(';')
                if len(cats) == 1:
                    print('Payee "{}" match "{}" with category '
                          '"{}"'.format(payee, self.payeeDict[key][0], cats[0]))
                    return cats[0]
                else:
                    i = 0
                    while i < len(cats):
                        if len(cats[i].split(',')) == 2:
                            (cat, cdatestr) = cats[i].split(',')
                            cdatestr = cdatestr+'31'
                            cat_date = datetime.datetime.strptime(
                                    cdatestr, '%Y%m%d').date()
                            if bud_date <= cat_date:
                                return cat
                            else:
                                i += 1
                        else:
                            # the last category is the most recent
                            return cats[i]

        #
        # If all else fails, return the default
        print 'Payee "'+payee+'" no match found'
        return 'UNKNOWN'

    def processBudgetFields(self, extfield, transAmt, defaultCat, transDate, \
            transRef):
        '''
        Each field in extfield can be like: 'BUDCAT[=BUDAMT[=BUDDATE]]', or
        'DATE=<BUDDATE>'
        '''
        budcat = ''
        budamt = ''
        buddat = ''
        idx = 0
        buddict = {}
        for field in extfield:
            subfield = field.split('=')
            if subfield[0] == 'DATE':
                if buddat:
                    buddict[idx] = [budcat, budamt, buddat]
                    budcat = ''
                    budamt = ''
                    buddat = ''
                    idx += 1
                else:
                    buddat = subfield[1]
            else:
                if budcat:
                    buddict[idx] = [budcat, budamt, buddat]
                    budcat = ''
                    budamt = ''
                    buddat = ''
                    idx += 1
                if len(subfield) == 1:
                    budcat = subfield[0]
                elif len(subfield) == 2:
                    budcat = subfield[0]
                    budamt = subfield[1]
                else:
                    budcat = subfield[0]
                    budamt = subfield[1]
                    buddat = subfield[2]

        # assign the last or only row
        buddict[idx] = [budcat, budamt, buddat]

        # finish processing missing budget info with (calculated) defaults
        tran_amt_isneg = float(transAmt) < 0.0

        # remainder is a double and is always POSITIVE
        remainder = abs(float(transAmt))

        for key, val in collections.OrderedDict(
                sorted(buddict.items())).iteritems():
            if not val[0]:
                buddict[key][0] = defaultCat # default

            # The assumption is that all budget amounts are positive, but use
            # the same sign as the transaction amount
            if not val[1]: # no budget amount?
                # assign any remainder to it
                buddict[key][1] = '%.2f' % (-1.0*remainder \
                        if tran_amt_isneg else remainder)
                remainder = 0.0
            else: # otherwise decrement remainder by the budget amount
                # keep track of the remainder
                remainder = remainder - float(val[1])
                if tran_amt_isneg and not buddict[key][1].startswith('-'):
                    buddict[key][1] = '-'+buddict[key][1]
                if remainder < 0.0: # something didn't add up
                    remainder = 0.0
                    print('Calculating amount for {} and got a remainder less t'
                          'han zero (transRef={}, extra fields='
                          '{})'.format(val, transRef, ','.join(extfield)))
            # end if
            if not val[2]: # no budget date?
                buddict[key][2] = transDate # assign transaction date
            # end if
        # end for
        return buddict

    def insertEntryIntoDict(self, buddict, transRef, transDate, transPayee, \
            transChecknum, transType, transAmt, transComment, outdict):
        if len(buddict) == 1: # there is only one line for this transaction
            bud = buddict[0]
            outdict[transRef] = [transDate, transRef, transPayee,
                                 transChecknum, transType, transAmt, bud[0],
                                 bud[1], bud[2], transComment]
        else:
            # print 'Multiline transaction: '+transRef,buddict
            for key, bud in collections.OrderedDict(
                    sorted(buddict.items())).iteritems():
                mykey = transRef + '-' + str(key)
                # print '  mykey='+mykey
                outdict[mykey] = [transDate, transRef, transPayee,
                                  transChecknum, transType, transAmt, bud[0],
                                  bud[1], bud[2], transComment]

    def readMonthlyCUFile(self, fname):
        '''
        The old format of the Credit Union output files of the C# budget program
        was the same as the download files and included many fields that are not
        used in budget calculations. This wasted time and space. More
        troublesome was that the output files did not include the calculated
        budget category.  This meant that the budget had to be looked up for
        almost EVERY RECORD in EVERY FILE, EVERY TIME the files were read in.
        This was a HUGE performance hit. The new files (for backup purposes)
        will have a different format: only the fields that are used will be
        saved, including the budget category. The only time the budget category
        will have to be looked up is when the download file is first processed
        to be added to the database.
        '''
        firstline = '"Transaction ID","Posting Date","Effective Date","Transaction Type","Amount","Check Number","Reference Number","Description","Transaction Category","Type","Balance"'
        #                          0              1               2                 3             4           5                6                 7                 8              9       10
        laterfirstline1 = '"Transaction ID","Posting Date","Effective Date","Transaction Type","Amount","Check Number","Reference Number","Payee","Memo","Transaction Category","Type","Balance"'
        #                          0              1               2                 3             4           5                6             7      8              9              10      11
        laterfirstline0 = '"Transaction_Date","Transaction_ID","TranDesc","ExtDesc","Description","Fee","Amount","Other_Charges","Balance","Post_Date","Check_Number"'
        #                          0                1             2          3           4         5      6           7             8          9            10
        earlyfirstline = '"Transaction_Date","Transaction_ID","Description","Fee","Amount","Other_Charges","Balance","Post_Date","Check_Number"'
        #                          0                1               2         3      4           5             6          7            8
        # There are many differences in the file format for CU after 1/25/2016.
        # All fields are book-ended by double-quotes
        #    Transaction ID: is a space-delimited field consisting of:
        #        Posting date (YYYYMMDD)
        #        454292 just those 6 digits, don't know what they are or if
        #              they will change in the future.
        #        Amount in pennies (absolute value, with commas every third
        #              digit)
        #        4 groups of three digits comma-delimited, eg, 201,601,088,564
        #            The 12 digits when concatenated are taken to be the Post
        #            Date as YYYYMMDD and old-format Transaction_ID minus the
        #            leading 'ID'.
        #            For example, 201,601,088,564 from above are combined
        #            together: 201601088564 and are interpreted as YYYYMMDDIIII,
        #            or '1/8/2016', 'ID8564'
        #    Posting Date: as M/D/YYYY
        #    Effective Date: as M/D/YYYY
        #    Transaction Type: as Debit, Credit, Check
        #    Amount: as [-]d+\.ddddd
        #    Check Number: (empty if Transaction Type is not Check)
        #    Reference Number: 9-digit, appears to be a unique number which
        #          decrements by one for every new transaction
        #    Description: Details of who
        #    Transaction Category: Mostly empty, but sometimes has a budget
        #          category (bank-assigned)
        #    Type: Debit Card, ACH, Withdrawal, Transfer, sometimes empty
        #    Balance: Amount remaining in checking account
        # The difference between the monthly file formats for CU between
        #      Mar2006 and Apr2006, is the later dates added two fields
        #      "TranDesc" and "ExtDesc"
        # The later records split the old Description field into TranDesc and
        #      ExtDesc, leaving the Description field the same as before
        olderformat = False
        linenum = 0
        expfields = 11
        outdict = {}
        with open(fname) as f:
            for line in f:
                desc = ''
                bud_cat = ''
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines
                #
                # First line stuff
                #
                if linenum == 0:
                    if line == firstline:
                        itdate = 1
                        itid = 6
                        iamt = 4
                        ichecknum = 5
                        ipayee = 7
                        linenum += 1
                    else:
                        print fname+' has unexpected header.'
                        self.unexpectedheader.append(path.basename(fname))
                        return dict()
                #
                # Process all other lines
                #
                else:
                    # Clear any commas inside quoted fields
                    line = self.clearCommasInQuotes(' ', line)

                    # Look for in-line comments and keep them
                    comment = ''
                    idx = line.find('//')
                    if idx >= 0:
                        comment = line[idx:]
                        line = line[:idx]

                    # remove all double-quote characters (by this point it is
                    # guarenteed that there are no extraneous commas)
                    line = line.translate(None, '"')

                    # split the line into fields (comma-separated)
                    field = line.split(',')

                    # verify there are no FEWER than the expected number of
                    # fields (can be greater)
                    if len(field) < expfields:
                        print('Missing fields in file {}. Expected at least {} '
                              'but got {}. Line:\n'
                              '{}'.format(fname, expfields, len(fields), line))
                        sys.exit(1)

                    if len(field[expfields:]) > 0:
                        comment = str(field[expfields:]) + comment

                    # parse the first field -- transaction date (split off time
                    # part)
                    trans_date = field[itdate].split(' ')[0] # default value

                    # Transaction ID
                    tid = field[itid]

                    # If the record is a check, use the checks database to fill
                    # in the budget fields
                    # For UNRECORDED checks, we will need to fill in budget
                    # fields with default values
                    checknum = ''
                    tpayee = field[ipayee]
                    bcaddict = dict()
                    if field[ichecknum]: # a check
                        # value of ichecknum depends on old or new format
                        checknum = field[ichecknum]

                        # There is a check in the CU database with number '1'.
                        # We're renumbering it for the database
                        if checknum == '1':
                            checknum = '999999'
                        # process the check
                        # desc, bcaddict = self.lookupCUCheckCat(
                        #             checknum, field[iamt], trans_date)
                        # desc = 'Check '+checknum+': '+desc

                        # The check info resides in the checks table. The
                        # 'main' entry for the check has no useful budget
                        # information.
                        desc = 'Check'
                        bcaddict[0] = ['XXX', 0, '']

                    # If the record is not a check, fill in the budget info
                    # from the payee database or optional extra budget fields
                    else:
                        # Lookup the default budget category from the payee
                        # database

                        # defaults to 'UNKNOWN'
                        bud_cat = self.lookupPayeeCat(tpayee, trans_date)

                        # set the default budget date and amount from the
                        # transaction date and amount
                        bud_date = trans_date
                        bud_amt = field[iamt]

                        # process the extra budget fields which may mean extra
                        # database records
                        bcaddict = self.processBudgetFields(
                                field[expfields:],
                                bud_amt,
                                bud_cat,
                                trans_date,
                                tid)

                    # end if

                    self.insertEntryIntoDict(
                        bcaddict,
                        tid,
                        trans_date,
                        desc if checknum else ' '.join(tpayee.split()) \
                                if tpayee else field[ipayee],
                        checknum,
                        'b',
                        field[iamt],
                        comment,
                        outdict)
                    linenum += 1
                # end if linenum == 0
            # end for each line
        # end with open

        print 'readMonthlyCUFile processed', linenum, 'records from '+fname+'\n'
        return outdict


    def readMonthlyAmexFile(self, fname):
        linenum = 0
        transactions = 0
        expfields = 5
        outdict = {}
        with open(fname) as f:
            for line in f:
                desc = ''
                bud_cat = ''
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clearCommasInQuotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is
                # guaranteed that there are no extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expfields:
                    print('Missing fields in file {}. Expected at least {} '
                          'but got {}. Line:\n'
                          '{}'.format(fname, expfields, len(field), line))
                    sys.exit(1)

                # parse the first field -- transaction date
                trans_date = field[0] # mm/dd/yyyy

                # parse the transaction reference
                trans_ref = field[1].split()[1]

                # transaction amount
                trans_amt = field[2]

                # transaction payee
                trans_payee = field[3]

                # Lookup the default budget category from the payee database
                # defaults to 'UNKNOWN'
                bud_cat = self.lookupPayeeCat(trans_payee, trans_date)

                # set the default budget date and amount from the transaction
                # date and amount
                bud_date = trans_date
                bud_amt = trans_amt

                # process the extra budget fields which may mean extra database
                # records
                bcaddict = self.processBudgetFields(
                        field[expfields:],
                        trans_amt,
                        bud_cat,
                        trans_date,
                        trans_ref)

                # insert the record(s) into the dictionary
                self.insertEntryIntoDict(
                        bcaddict,
                        trans_ref,
                        trans_date,
                        trans_payee,
                        '',
                        'x',
                        trans_amt,
                        comment,
                        outdict)
                linenum += 1
            # end for
        print('readMonthlyAmexFile processed {} records from {}\n'.format(linenum, fname))
        return outdict

    def readMonthlyCitiFile(self, fname):
        '''
        Citi Card took over all Costco American Express card accounts on
        June 3, 2016. Citi has all historical Costco AMEX card transactions
        back to May 2014, if needed.
        But those Amex-era download formats will be in the earlier Citi
        download format, not the former Amex format.

        On or before 06/02/2016:
            0                     1                   2                                                       3               4             5
        "Status",               "Date",         "Description",                                              "Debit",       "Credit",   "Member Name"
        "Cleared",           "06/02/2016",       "E 470 EXPRESS TOLLS                     ",               "32.55",           "",      "CHRIS ANDERSON"

        On or after 06/03/2016 ('newformat'):
            0                     1                   2                                                       3               4             5
        "Status",               "Date",         "Description",                                              "Debit",       "Credit",   "Member Name"
        "Cleared",           "06/03/2016",       "AMAZON.COM                           XXXX-XXXX-XXXX-3003","8.65",           "",      "KATHY ANDERSON"

            0                     1                   2                                                        3               4
        "Status",               "Date",         "Description",                                              "Debit",       "Credit"
        "Cleared",           "11/30/2016",      "KING SOOPERS #0729 FUEL  ERIE         CO",                    "",          "22.88"


        The only difference between the two formats is very small: The earlier
        format does not have the crypto-card number at the end of the
        description field.
        Both Debit and Credit values are positive.

        TODO: Talk to Citi about adding transaction reference field to download
        file
        DONE: Talked to Citi about adding transaction ID field. They have
        passed the request on to their tech guys.
        '''

        linenum = 0
        transactions = 0
        expfields = 6
        outdict = {}
        with open(fname) as f:
            for line in f:
                desc = ''
                bud_cat = ''

                # strip all leading and trailing spaces and new-lines
                line = line.rstrip().lstrip()

                # ignore blank lines
                if not line: continue

                # Clear any commas inside quoted fields
                line = self.clearCommasInQuotes('', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is
                # guaranteed that there are no extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # skip if it's the header line
                if 'status' in field[0].lower(): continue

                # Skip if it's a pending transaction. Sometimes transaction
                # details change when they transition from Pending to Cleared
                # and a slightly different form of the exact same transaction
                # is created and inserted into the database the next time the
                # Citi transaction file is downloaded and processed by this
                # script, creating a double entry. To prevent this, only
                # consider Cleared transactions which by assumption do not
                # change over time.
                if 'pending' in field[0].lower(): continue

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expfields:
                    print('Missing fields in file {}. Expected at least {} but '
                          'got {}. Line:\n'
                          '{}'.format(fname, expfields, len(field), line))
                    sys.exit(1)

                # parse the second field -- transaction date
                trans_date = field[1] # mm/dd/yyyy
                tdate = datetime.datetime.strptime(
                        trans_date, "%m/%d/%Y").date()
                newformat = False

                # all dates > 6/2/2016 are newformat
                if tdate > datetime.datetime.strptime(
                        '6/2/2016', '%m/%d/%Y').date():
                    newformat = True

                # parse the transaction reference
                # trans_ref = field[1].split()[1]

                # transaction amount (fields 3 and 4 are mutually exclusive:
                # one or the other has a value, not both)
                if field[3]:
                    trans_amt = '-'+field[3] # Debits need to be negative value
                else:
                    trans_amt = field[4]

                # transaction payee
                trans_payee = field[2]

                # strip-off optional credit card number at end of field
                if newformat:
                    # strip off crypto-card-number
                    trans_payee = trans_payee[0:37]

                # strip off any and all trailing white-space
                trans_payee = trans_payee.rstrip()

                # Lookup the default budget category from the payee database
                # defaults to 'UNKNOWN'
                bud_cat = self.lookupPayeeCat(trans_payee, trans_date)

                # set the default budget date and amount from the transaction
                # date and amount
                bud_date = trans_date
                bud_amt = trans_amt

                # TEMP: create a transaction reference from the value of each
                # field. Empty fields get a # value
                hashkey = trans_date+trans_amt+trans_payee+field[5]
                trans_ref = hashlib.md5(hashkey).hexdigest()
                print hashkey+' => '+trans_ref

                # process the extra budget fields which may mean extra database
                # records
                bcaddict = self.processBudgetFields(
                        field[expfields:], trans_amt, bud_cat, trans_date,
                        trans_ref)

                # insert the record(s) into the dictionary
                self.insertEntryIntoDict(bcaddict, trans_ref, trans_date,
                                         trans_payee, '', 'C', trans_amt,
                                         comment, outdict)
                linenum += 1
            # end for
        print('readMonthlyCitiFile processed {} records from {}'
              '\n'.format(linenum, fname))
        return outdict


    def readMonthlyDiscoverFile(self, fname, download=False):
        '''
        There are two formats for Discover files, one for downloads, and the
        other for legacy monthly files
        '''
        #      0-2       3-5                6                                                          7        8
        # 2012,08,07,2012,08,07,PANANG THAI CUISINE LAFAYETTE CO,                                     -26,   Restaurants
        # 2007,10,16,2007,10,16,SAFEWAY STORE 1552 FORT COLLINS CO CASHOVER $ 20.00 PURCHASES $ 14.47,-34.47,Supermarkets
        #    tdate      xxxx              tpayee                                                       tamt  payee type
        #
        # example download file (note date format change and quotation marks):
        #      0         1                  2                                 3       4
        # 07/07/2015,07/07/2015,"MT RUSHMORE KOA/PALMER HILL CITY SD00797R",62.24,"Services"
        #    tdate                        tpayee                            tamt  payee type
        #
        # Discover card is the only one that does not use a unique identifier
        # for every transaction. We have to create one that is not
        # fool-proof: combine the 2 dates, payee, amount, and payee type with
        # all the spaces removed. Most of the time the resulting string is
        # unique. But once in a while two or more transactions occur on the
        # same day to the same payee for the same amount and then they have to
        # be distinguished. This is problematic.

        linenum = 0
        transactions = 0
        expfields = 5 if download else 9
        checkdict = {}
        outdict = {}
        with open(fname) as f:
            for line in f:
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines
                # print 'Discover: '+line
                if line.startswith('<!--'):
                    print 'readMonthlyDiscoverFile: Skipping line "'+line+'"'
                    continue

                # download files have header line; legacy monthly files do not
                if linenum == 0 and download:
                    # This is the file when there are no transactions in the
                    # given period
                    if line.startswith('There are no statements'):
                        return outdict

                    fields = line.split(',')
                    if len(fields) != expfields:
                        print('Discover download file header line has {} field('
                              's) instead of expected '
                              '{}'.format(len(fields), expfields))
                        sys.exit(1)
                    linenum += 1
                    continue
                desc = ''
                bud_cat = ''
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clearCommasInQuotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is
                # guaranteed that there are no extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expfields:
                    print('Missing fields in file {}. Expected at least {} but '
                          'got {}. Line:\n'
                          '{}'.format(fname, expfields, len(field), line))
                    sys.exit(1)

                # parse the first field -- transaction date
                if download:
                    trans_date = field[0]
                else:
                    trans_date = field[1]+'/'+field[2]+'/'+field[0]

                # parse the transaction amount
                # Discover reverses the sign of the amounts: no sign (positive)
                # for debits, - for credits -- we reverse it to preserve
                # consistency across accounts
                if download:
                    tamt = float(field[3])
                    trans_amt = '%.2f' % -tamt
                else:
                    tamt = float(field[7])
                    trans_amt = '%.2f' % tamt

                    # this converts amounts like '-7.1' to a consistent '-7.10'
                    field[7] = trans_amt

                # parse the transaction reference
                # some work here to get the dates in the right order and format
                if download:
                    date1 = field[0].split('/')
                    date2 = field[1].split('/')
                    trans_ref = ''.join([''.join([date1[2],
                                                  date1[0],
                                                  date1[1]]),
                                         ''.join([date2[2],
                                                  date2[0],
                                                  date2[1]]),
                                         field[2].replace(' ', ''),
                                         trans_amt,
                                         field[4].replace(' ', '')])
                else:
                    # The reference will be the entire line stripped of commas
                    # and spaces, minus any extra fields
                    trans_ref = ''.join(field[:expfields]).replace(' ', '')

                # checkdict is here to make sure the record reference is unique
                while trans_ref in checkdict:
                    print('Discover transaction reference "{}" is not unique. A'
                          'ppending "x" to it'.format(trans_ref))
                    # If it's already being used, add a character to it
                    trans_ref = trans_ref + 'x'

                # now the reference is unique and can be inserted into the
                # database
                checkdict[trans_ref] = 0

                # transaction payee
                if download:
                    trans_payee = field[2]
                else:
                    trans_payee = field[6]

                # Lookup the default budget category from the payee database
                # defaults to 'UNKNOWN'
                bud_cat = self.lookupPayeeCat(trans_payee, trans_date)

                # set the default budget date and amount from the transaction
                # date and amount
                bud_date = trans_date
                bud_amt = trans_amt

                # process the extra budget fields which may mean extra database
                # records
                bcaddict = self.processBudgetFields(
                    field[expfields:], trans_amt, bud_cat, trans_date,
                    trans_ref)

                # insert the record(s) into the dictionary
                self.insertEntryIntoDict(
                    bcaddict, trans_ref, trans_date, trans_payee, '', 'd',
                    trans_amt, comment, outdict)
                linenum += 1
            # end for
        print('readMonthlyDiscoverFile processed {} records from {}\n'.format(linenum, fname))
        return outdict



    def readMonthlyChaseFile(self, fname):
        #   0            1                                     2                                       3
        # CREDIT,20100216120000[0:GMT],"Online Transfer from  MMA XXXXXX6306 transaction#: 313944149",19.79
        # DEBIT,20100212120000[0:GMT],"MCDONALD'S F109 BOULDER         02/11MCDONALD'",              -1.08
        # CHECK,20100216120000[0:GMT],"CHECK 1108",                                                  -90.00
        # trtype       tdatetime                           payee                                      tamt
        linenum = 0
        expfields = 4
        outdict = dict()
        with open(fname) as f:
            for line in f:
                desc = ''
                bud_cat = ''
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clearCommasInQuotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is
                # guaranteed that there are no extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expfields:
                    print('Missing fields in file {}. Expected at least {} but got {}. Line:\n{}'.format(fname, expfields, len(field), line))
                    sys.exit(1)

                # parse the date field -- transaction date
                trans_date = field[1][4:6]+'/'+field[1][6:8]+'/'+field[1][0:4]

                # parse the transaction reference
                # The reference will be the entire line stripped of commas and
                # spaces
                trans_ref = line.replace(',', '').replace(' ', '')

                # transaction amount
                trans_amt = field[3]

                # transaction payee
                # strip out extra spaces
                trans_payee = ' '.join(field[2].split())

                # Lookup the default budget category from the payee database
                # defaults to 'UNKNOWN'
                bud_cat = self.lookupPayeeCat(trans_payee, trans_date)

                # set the default budget date and amount from the transaction
                # date and amount
                bud_date = trans_date
                bud_amt = trans_amt

                # process the extra budget fields which may mean extra database
                # records
                bcaddict = self.processBudgetFields(
                    field[expfields:], trans_amt, bud_cat, trans_date,
                    trans_ref)

                # insert the record(s) into the dictionary
                self.insertEntryIntoDict(
                    bcaddict, trans_ref, trans_date, trans_payee, '', 'c',
                    trans_amt, comment, outdict)
                linenum += 1
            # end for
        print('readMonthlyChaseFile processed {} records from {}\n'.format(linenum, fname))
        return outdict



    def readDownloadBarclayFile(self, fname):
        # This is the download file format:
        #
        # ...<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20150203050000.000<DTUSER>20150203050000.000<TRNAMT>566.64<FITID>75140215034020315130448108<NAME>PAYMENT RECV'D CHECKFREE</STMTTRN>...
        #
        linenum = 0
        outdict = dict()
        with open(fname) as f:
            for line in f:
                if '<STMTTRN>' in line:
                    transactions = line.split('<STMTTRN>')
                    # for each transaction (element 0 does not contain what we
                    # are looking for)
                    for trans in transactions[1:]:
                        if not '<DTPOSTED>' in trans or \
                                not '<TRNAMT>' in trans or \
                                not '<FITID>' in trans or \
                                not '<NAME>' in trans:
                            print('Missing fields in file {}. Expected 4 fields, but one or more are missing: {}'.format(fname, trans))
                            sys.exit(1)
                        matchobj = re.search(r'<FITID>([^<]+)<', trans)
                        if matchobj:
                            trans_ref = matchobj.group(1)
                        else:
                            print('Error matching <FITID> in transaction "{}" in file {}'.format(trans, fname))
                            sys.exit(1)
                        matchobj = re.search(r'<DTPOSTED>([^<]+)<', trans)
                        if matchobj:
                            trans_date = (matchobj.group(1)[4:6]+'/'+
                                          matchobj.group(1)[6:8]+'/'+
                                          matchobj.group(1)[:4])
                        else:
                            print('Error matching <DTPOSTED> in transaction "{}" in file {}'.format(trans, fname))
                            sys.exit(1)
                        matchobj = re.search(r'<TRNAMT>([^<]+)<', trans)
                        if matchobj:
                            trans_amt = matchobj.group(1)
                        else:
                            print('Error matching <TRNAMT> in transaction "{}" in file {}'.format(trans, fname))
                            sys.exit(1)
                        matchobj = re.search(r'<NAME>([^<]+)<', trans)
                        if matchobj:
                            trans_payee = matchobj.group(1)
                        else:
                            print('Error matching <NAME> in transaction "{}" in file {}'.format(trans, fname))
                            sys.exit(1)

                        # lookup the default budget category from the payee database
                        # defaults to 'UNKNOWN'
                        bud_cat = self.lookupPayeeCat(trans_payee, trans_date)

                        # set the default budget date and amount from the
                        # transaction date and amount
                        bud_date = trans_date
                        bud_amt = trans_amt

                        # insert the record(s) into the dictionary
                        bcaddict = dict()
                        bcaddict[0] = [bud_cat, bud_amt, bud_date]
                        self.insertEntryIntoDict(
                            bcaddict, trans_ref, trans_date, trans_payee, '',
                            'y', trans_amt, '', outdict)
                        linenum += 1
                    # end for each transaction
                # end if <STMTTRN> found in line
            # end for each line in file
        print('readDownloadBarclayFile processed {} records from '
              '{}\n'.format(linenum, fname))
        return outdict

    def readMonthlyBarclayFile(self, fname):
        # This is the monthly file format:
        #   0  1  2             3                      4         5
        # 2011,04,04,252478010910000016899273001,BOMBAY MASALA,31.00
        # tyr tmo tday         tref                  payee      tamt
        linenum = 0
        expfields = 6
        outdict = {}
        with open(fname) as f:
            for line in f:
                desc = ''
                bud_cat = ''
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clearCommasInQuotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is
                # guaranteed that there are no extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expfields:
                    print('Missing fields in file {}. Expected at least {} but '
                          'got {}. Line:\n{}'.format(fname, expfields,
                                                     len(field), line))
                    sys.exit(1)

                # parse the date field -- transaction date
                trans_date = field[1]+'/'+field[2]+'/'+field[0]

                # parse the transaction reference
                trans_ref = field[3]

                # transaction amount
                # all transaction amounts shown as a positive number
                trans_amt = field[5]

                # transaction payee
                # strip out extra spaces
                trans_payee = ' '.join(field[4].split())

                # lookup the default budget category from the payee database
                # defaults to 'UNKNOWN'
                bud_cat = self.lookupPayeeCat(trans_payee, trans_date)

                # set the default budget date and amount from the transaction
                # date and amount
                bud_date = trans_date
                bud_amt = trans_amt

                # process the extra budget fields which may mean extra database
                # records
                bcaddict = self.processBudgetFields(
                    field[expfields:], trans_amt, bud_cat, trans_date,
                    trans_ref)

                # insert the record(s) into the dictionary
                self.insertEntryIntoDict(
                    bcaddict, trans_ref, trans_date, trans_payee, '', 'y',
                    trans_amt, comment, outdict)
                linenum += 1
            # end for
        print('readMonthlyBarclayFile processed {} records from {}\n'.format(linenum, fname))
        return outdict


    def processFile(self, fname):
        local_inserted = 0

        if not fname.endswith('.txt'): return
        if fname.endswith('cat.txt'): return
        if fname.endswith('DB.txt'): return
        if '2004' in fname or '2005' in fname: return
        print 'Processing file '+fname
        if 'Discover' in fname:
            outdict = self.readMonthlyDiscoverFile('decoded-dbs/'+fname)
        elif 'Amex' in fname:
            outdict = self.readMonthlyAmexFile('decoded-dbs/'+fname)
        elif 'Chase' in fname:
            outdict = self.readMonthlyChaseFile('decoded-dbs/'+fname)
        elif 'Barclay' in fname:
            outdict = self.readMonthlyBarclayFile('decoded-dbs/'+fname)
        else:
            outdict = self.readMonthlyCUFile('decoded-dbs/'+fname)

        for key, val in outdict.iteritems():
            record = ('INSERT into main (tran_date, tran_ID, tran_desc, tran_ch'
                      'ecknum, tran_type, tran_amount, bud_category, bud_amount'
                      ', bud_date, comment) VALUES (STR_TO_DATE("'+val[0]+'","%'
                      'm/%d/%Y"), "'+key+'", "'+val[2]+'", "'+val[3]+'", "'+
                      val[4]+'", "'+val[5]+'", "'+val[6]+'", "'+val[7]+'", STR_'
                      'TO_DATE("'+val[8]+'","%m/%d/%Y"), "'+val[9]+'");')
            self.cur.execute(record)
            local_inserted += 1

        print 'Inserted', local_inserted, 'records into database'
        self.inserted += local_inserted
        self.totalfiles += 1
        self.filesprocessed += 1

        return

    def mergeOTCChecks(self):
        for fname in glob.glob('decoded-dbs/*.txt'):
            if '2004' in fname or '2005' in fname: continue
            if 'Discover' in fname: continue
            if 'Amex' in fname: continue
            if 'Chase' in fname: continue
            if 'Barclay' in fname: continue
            if fname.endswith('cat.txt'): continue
            if fname.endswith('DB.txt'): continue

            # We are left with credit union files
            outdict = self.readMonthlyCUFile(fname)
            for key, val in outdict.iteritems():
                # outdict[transRef] = [transDate, transRef, transPayee,
                #                      transChecknum, transType, transAmt,
                #                      bud[0], bud[1], bud[2], transComment]
                if val[3].strip(): # Check number is not empty
                    self.cur.execute("select tran_checknum from main where tran"
                                     "_ID = '"+key+"';")
                    self.cur.fetchone()
                    for row in self.cur:
                        # Check number field does not exist in database for
                        # this transaction
                        if row[0] == 0:
                            query = ("update main set tran_checknum = '"+val[3]+
                                     "',tran_desc = '"+val[2]+"' where tran_ID "
                                     "= '"+key+"';")
                            print query
                            self.cur.execute(query)
