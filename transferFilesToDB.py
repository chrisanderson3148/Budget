"""Module contains methods to etc"""

from __future__ import print_function
import sys
import re
import datetime
import glob
import json
from os import path
from warnings import filterwarnings
import collections
import pprint
import hashlib
import MySQLdb as Database
from transferPayee import TransferPayee

filterwarnings('ignore', category=Database.Warning)

# Formats of output monthly files by source for one-time transfer to DATABASE.
#  Credit Union -- header line and 11 double-quoted, comma-separated fields
#  "Transaction_Date","Transaction_ID","TranDesc","ExtDesc","Description","Fee","Amount","Other_Charges","Balance","Post_Date","Check_Number"
#  "7/1/2015 7:50:12 AM","ID8265","ACH Debit","MGMT SPECIALISTS  - ONLINE PMT","ACH Debit MGMT SPECIALISTS  - ONLINE PMT","","-72","","9243.05","7/1/2015",""
#  American Express -- no header line, 5 fields, some double-quoted, all comma-separated.
#    07/02/2015,"Reference: 320151840289924743",32.52,"TJ MAXX #803 00000088009266299","080305055978009266299"
#  Discover -- no header line, 9 fields, none double-quoted, all comma-separated.
#    2015,07,07,2015,07,07,MT RUSHMORE KOA/PALMER HILL CITY SD00797R,-62.24,Services,TRAVEL
#  Barclay -- no header line, 6 fields, none double-quoted, all comma-separated.
#    2015,02,03,751402150340203151304480108,PAYMENT RECV'D CHECKFREE,566.64

# The common fields from the download files are tran_date, tran_ID, tran_desc, tran_amount
# Discover does not have a transaction ID. Historically it's been created as a concatenation of all the
#   field values together.
# The main DATABASE table will also include 3 additional fields: bud_category, bud_amount, bud_date
# Normally each record when imported will copy tran_amount to bud_amount, and tran_date to bud_date. The
#   bud_cat field will be filled in by a lookup to the payee table, or if it is a check, from the check
#   table. The tran_desc field will be matched with a known budget category from the payee table or from
#   the check table. If a result is not found in the payee table, then "UNKNOWN" will be entered for
#   bud_category.
# Occasionally there are extra fields in the monthly files, after the default fields. They are for
#   budget override purposes. They can override the budget category, budget date, and/or budget amount.
#   If it overrides the amount, then multiple records with the same
#   tran_date/tran_ID/tran_desc/tran_amount are created, but with different bud_category, bud_date, and
#   bud_amount. These records are connected together by the tran_ID. If a change to the budget
#   date/category/amount is made to any of them, the old set is deleted, and a new set with the changed
#   data is created to replace it.

class TransferMonthlyFilesToDB(object):
    """Class to transfer monthly files to DATABASE

    :param Any cursor: the DATABASE CURSOR object
    """

    def __init__(self, cursor):
        self.cur = cursor
        # Initialize payee table
        payee = TransferPayee()
        self.payee_dict = payee.read_payee_file('payee')
        with open('payroll_ignore_transfer.json') as data_file:
            self.payroll_ignore_transfer_dict = json.load(data_file)
        self.pretty_print = pprint.PrettyPrinter(indent=4)
        self.pretty_print.pprint(self.payee_dict)
        self.unexpected_header = []
        self.total_files = 0
        self.files_processed = 0
        self.inserted = 0

    def results(self):
        """Just returns a tuple of total_files, files_processed, inserted, and unexpected_header

        :rtype: tuple
        """
        return self.total_files, self.files_processed, self.inserted, self.unexpected_header

    def clear_commas_in_quotes(self, replace_char, line):
        """Replaces all commas ',' inside double-quotes with the given replacement character.
        Returns the same line with all the bad commas replaced.

        :param str replace_char: the character to replace the bad comma
        :param str line: the line containing the potentially bad comma(s)
        :rtype: str
        """
        start = 0
        while line.find('"', start) != -1:
            idx1 = line.find('"', start)  # index of opening quote
            if idx1 == -1:
                break
            idx2 = line.find('"', idx1+1)  # index of closing quote
            if idx2 == -1:  # Didn't find a closing quote? Barf
                print('Improperly formed line: opening " but no closing " in line\n{}'.format(line))
                sys.exit(1)

            # replace all found commas with replace_char within the opening and closing quotes
            while True:
                comma_index = line.find(',', idx1, idx2)
                if comma_index >= 0:  # replace found comma with replacement char
                    line = line[:comma_index] + replace_char + line[comma_index + 1:]
                else:  # found all commas (or there were none)
                    break

            # move after closing quote to begin another search for an opening quote
            start = idx2 + 1
        # now line is clear of confusing commas
        line = line.translate(None, '"')  # remove all double-quotes
        return line

    def pretty(self, the_dict, indent=0):
        """Recursively prints the elements of the given dictionary

        :param dict the_dict: the dictionary to print
        :param int indent: the number of spaces to indent each new level (default = 0)
        """
        for key, value in the_dict.iteritems():
            # if indent == 0: print '\n'
            print('  ' * indent + str(key))
            if isinstance(value, dict):
                self.pretty(value, indent+1)
            else:
                print('  ' * (indent+1) + str(value))

    def lookup_credit_union_check_category(self, check_num, amount, transaction_date):
        """Return the payee and budget dictionary for the given check number

        :param str check_num: the check number as a string
        :param str amount: the check amount as a string
        :param str transaction_date: the check transaction date as a string
        :rtype: tuple
        """
        budget_dict = {}
        payee = 'Unknown'
        self.cur.execute('SELECT tnum,tpayee,bud_cat,bud_amt,bud_date FROM checks WHERE tchecknum = "'
                         + check_num + '" order by tnum;')
        if self.cur.rowcount > 0:
            for row in self.cur:
                # print check_num, row
                if len(row[0].split('-')) > 1:
                    key = int(row[0].split('-')[1])
                else:
                    key = 0
                payee = row[1]
                budget_category = row[2] if row[2] else 'UNKNOWN'
                budget_amount = str(row[3]) if not row[3] is None and row[3] > 0.0 else amount
                budget_date = row[4].strftime('%m/%d/%Y') if not row[4] is None else transaction_date
                budget_dict[key] = [budget_category, budget_amount, budget_date]
        else:
            print('No matching check ' + check_num + ' found in checks DATABASE')
            budget_dict[0] = ['UNKNOWN', amount, transaction_date]
        return payee, budget_dict

    def lookup_payee_category(self, payee, budget_date):
        """Return a budget category based on the payee string passed in, and the budget date

        Budget assignments based on the payee string change over time. That's why the budget date is
        needed to differentiate which budget category is returned.

        format examples: cat
                         cat1,date1;cat2,date2;...;catN
        The assumption is that each succeeding date is later than the
        preceding ones and that the last category applies to all later dates

        :param str payee: the payee string
        :param str budget_date: the budget date string
        :rtype: str
        """
        bud_date = datetime.datetime.strptime(budget_date, "%m/%d/%Y").date()

        # Match PAYROLL, IGNORE, and TRANSFER budget categories
        for key in self.payroll_ignore_transfer_dict:
            if key in payee:
                category = self.payroll_ignore_transfer_dict[key]
                print('Payee "{}" match "{}" with category "{}"'.format(payee, key, category))
                return category

        print('No payroll/ignore/transfer match found in "{}"'.format(payee))
        if 'transfer' in payee.lower():
            return 'TRANSFER'

        #
        # If not a standard, hard-coded budget category, try looking up in the payee DATABASE dictionary
        for key in sorted(self.payee_dict):
            match_object = re.match(self.payee_dict[key][0], payee, re.I)
            if match_object:
                cats = self.payee_dict[key][1].split(';')
                if len(cats) == 1:
                    print('Payee "{}" match "{}" with category "{}"'.format(payee,
                                                                            self.payee_dict[key][0],
                                                                            cats[0]))
                    return cats[0]
                else:
                    i = 0
                    while i < len(cats):
                        if len(cats[i].split(',')) == 2:
                            (cat, cat_date_string) = cats[i].split(',')
                            cat_date_string = cat_date_string+'31'
                            cat_date = datetime.datetime.strptime(cat_date_string, '%Y%m%d').date()
                            if bud_date <= cat_date:
                                return cat
                            else:
                                i += 1
                        else:
                            # the last category is the most recent
                            return cats[i]

        #
        # If all else fails, return the default
        print('Payee "'+payee+'" no match found')
        return 'UNKNOWN'

    def process_budget_fields(self, extra_field, transaction_amount, default_category, transaction_date,
                              transaction_reference):
        """Process the budget fields in the payee file (???)
        Returns a dictionary of the payee file

        Each field in extra_field can be like: 'BUDCAT[=BUDAMT[=BUDDATE]]', or 'DATE=<BUDDATE>'

        :param str extra_field:
        :param str transaction_amount:
        :param str default_category:
        :param str transaction_date:
        :param str transaction_reference:
        :rtype: dict
        """
        budget_category = ''
        budget_amount = ''
        budget_date = ''
        idx = 0
        budget_dict = {}
        for field in extra_field:
            subfield = field.split('=')
            if subfield[0] == 'DATE':
                if budget_date:
                    budget_dict[idx] = [budget_category, budget_amount, budget_date]
                    budget_category = ''
                    budget_amount = ''
                    budget_date = ''
                    idx += 1
                else:
                    budget_date = subfield[1]
            else:
                if budget_category:
                    budget_dict[idx] = [budget_category, budget_amount, budget_date]
                    budget_category = ''
                    budget_amount = ''
                    budget_date = ''
                    idx += 1
                if len(subfield) == 1:
                    budget_category = subfield[0]
                elif len(subfield) == 2:
                    budget_category = subfield[0]
                    budget_amount = subfield[1]
                else:
                    budget_category = subfield[0]
                    budget_amount = subfield[1]
                    budget_date = subfield[2]

        # assign the last or only row
        budget_dict[idx] = [budget_category, budget_amount, budget_date]

        # finish processing missing budget info with (calculated) defaults
        tran_amt_isneg = float(transaction_amount) < 0.0

        # remainder is a double and is always POSITIVE
        remainder = abs(float(transaction_amount))

        for key, val in collections.OrderedDict(sorted(budget_dict.items())).iteritems():
            if not val[0]:
                budget_dict[key][0] = default_category  # default

            # The assumption is that all budget amounts are positive, but use
            # the same sign as the transaction amount
            if not val[1]:  # no budget amount?
                # assign any remainder to it
                budget_dict[key][1] = '%.2f' % (-1.0*remainder if tran_amt_isneg else remainder)
                remainder = 0.0
            else:  # otherwise decrement remainder by the budget amount
                # keep track of the remainder
                remainder = remainder - float(val[1])
                if tran_amt_isneg and not budget_dict[key][1].startswith('-'):
                    budget_dict[key][1] = '-'+budget_dict[key][1]
                if remainder < 0.0:  # something didn't add up
                    remainder = 0.0
                    print('Calculating amount for {} and got a remainder less than zero (transaction_'
                          'reference={}, extra fields={})'.format(val, transaction_reference, ','
                                                                  .join(extra_field)))
            # end if
            if not val[2]: # no budget date?
                budget_dict[key][2] = transaction_date # assign transaction date
            # end if
        # end for
        return budget_dict

    def insert_entry_into_dict(self, budget_dict, transaction_reference, transaction_date,
                               transaction_payee, transaction_check_num, transaction_type,
                               transaction_amount, transaction_comment, output_dict):
        """Insert the transaction (possibly multi-budget) in to the output_dict dictionary

        :param dict budget_dict:
        :param str transaction_reference:
        :param str transaction_date:
        :param str transaction_payee:
        :param str transaction_check_num:
        :param str transaction_type:
        :param str transaction_amount:
        :param str transaction_comment:
        :param dict output_dict:
        :return:
        """
        if len(budget_dict) == 1:  # there is only one line for this transaction
            bud = budget_dict[0]
            output_dict[transaction_reference] = [transaction_date, transaction_reference,
                                                  transaction_payee, transaction_check_num,
                                                  transaction_type, transaction_amount,
                                                  bud[0], bud[1], bud[2], transaction_comment]
        else:
            for key, bud in collections.OrderedDict(sorted(budget_dict.items())).iteritems():
                my_key = transaction_reference + '-' + str(key)
                output_dict[my_key] = [transaction_date, transaction_reference, transaction_payee,
                                       transaction_check_num, transaction_type, transaction_amount,
                                       bud[0], bud[1], bud[2], transaction_comment]

    def read_monthly_cu_file(self, file_name):
        """Read in the downloaded Credit Union file line-by-line, and insert transactions in a dictionary
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Credit Union download file
        :rtype: dict
        """
        '''
        The old format of the Credit Union output files of the C# budget program was the same as the
        download files and included many fields that are not used in budget calculations. This wasted
        time and space. More troublesome was that the output files did not include the calculated budget
        category.  This meant that the budget had to be looked up for almost EVERY RECORD in EVERY FILE,
        EVERY TIME the files were read in.  This was a HUGE performance hit. The new files (for backup
        purposes) will have a different format: only the fields that are used will be saved, including
        the budget category. The only time the budget category will have to be looked up is when the
        download file is first processed to be added to the DATABASE.
        '''
        first_line = '"Transaction ID","Posting Date","Effective Date","Transaction Type","Amount",' \
                     '"Check Number","Reference Number","Description","Transaction Category","Type",' \
                     '"Balance"'

        later_first_line_1 = '"Transaction ID","Posting Date","Effective Date","Transaction Type",' \
                             '"Amount","Check Number","Reference Number","Payee","Memo",' \
                             '"Transaction Category","Type","Balance"'

        later_first_line_0 = '"Transaction_Date","Transaction_ID","TranDesc","ExtDesc","Description",' \
                             '"Fee","Amount","Other_Charges","Balance","Post_Date","Check_Number"'

        early_first_line = '"Transaction_Date","Transaction_ID","Description","Fee","Amount",' \
                           '"Other_Charges","Balance","Post_Date","Check_Number"'

        # There are many differences in the file format for CU after 1/25/2016.
        # All fields are book-ended by double-quotes
        #    Transaction ID: is a space-delimited field consisting of:
        #        Posting date (YYYYMMDD)
        #        454292 just those 6 digits, don't know what they are or if they will change in the
        #          future.
        #        Amount in pennies (absolute value, with commas every third digit)
        #        4 groups of three digits comma-delimited, eg, 201,601,088,564
        #            The 12 digits when concatenated are taken to be the Post
        #            Date as YYYYMMDD and old-format Transaction_ID minus the leading 'ID'.
        #            For example, 201,601,088,564 from above are combined together: 201601088564 and are
        #              interpreted as YYYYMMDDIIII, or '1/8/2016', 'ID8564'
        #    Posting Date: as M/D/YYYY
        #    Effective Date: as M/D/YYYY
        #    Transaction Type: as Debit, Credit, Check
        #    Amount: as [-]d+\.ddddd
        #    Check Number: (empty if Transaction Type is not Check)
        #    Reference Number: 9-digit, appears to be a unique number which decrements by one for every
        #      new transaction
        #    Description: Details of who
        #    Transaction Category: Mostly empty, but sometimes has a budget category (bank-assigned)
        #    Type: Debit Card, ACH, Withdrawal, Transfer, sometimes empty
        #    Balance: Amount remaining in checking account
        # The difference between the monthly file formats for CU between Mar2006 and Apr2006, is the
        #   later dates added two fields
        #      "TranDesc" and "ExtDesc"
        # The later records split the old Description field into TranDesc and ExtDesc, leaving the
        #   Description field the same as before
        line_num = 0
        expected_fields = 11
        output_dict = {}
        with open(file_name) as file_ptr:
            for line in file_ptr:
                desc = ''
                bud_cat = ''
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines
                #
                # First line stuff
                #
                if line_num == 0:
                    if line == first_line:
                        index_transaction_date = 1
                        index_transaction_id = 6
                        index_transaction_amount = 4
                        index_transaction_check_num = 5
                        index_payee = 7
                        line_num += 1
                    else:
                        print('###############################################')
                        print('###############################################')
                        print('###############################################')
                        print
                        print(fname+' has unexpected header.')
                        print('expected/got\n{}\n{}'.format(firstline, line))
                        print
                        print('###############################################')
                        print('###############################################')
                        print('###############################################')
                        
                        self.unexpectedheader.append(path.basename(fname))
                        return dict()
                #
                # Process all other lines
                #
                else:
                    # Clear any commas inside quoted fields
                    line = self.clear_commas_in_quotes(' ', line)

                    # Look for in-line comments and keep them
                    comment = ''
                    idx = line.find('//')
                    if idx >= 0:
                        comment = line[idx:]
                        line = line[:idx]

                    # remove all double-quote characters (by this point it is guarenteed that there are
                    # no extraneous commas)
                    line = line.translate(None, '"')

                    # split the line into fields (comma-separated)
                    fields = line.split(',')

                    # verify there are no FEWER than the expected number of fields (can be greater)
                    if len(fields) < expected_fields:
                        print('Missing fields in file {}. Expected at least {} but got {}. Line:\n{}'
                              .format(file_name, expected_fields, len(fields), line))
                        sys.exit(1)

                    if fields[expected_fields:]:
                        comment = str(fields[expected_fields:]) + comment

                    # parse the first field -- transaction date (split off time part)
                    trans_date = fields[index_transaction_date].split(' ')[0]  # default value

                    # Transaction ID
                    tid = fields[index_transaction_id]

                    # If the record is a check, use the checks DATABASE to fill in the budget fields
                    # For UNRECORDED checks, we will need to fill in budget fields with default values
                    check_num = ''
                    transaction_payee = fields[index_payee]
                    budget_category_dict = dict()
                    if fields[index_transaction_check_num]:  # a check
                        # value of index_transaction_check_num depends on old or new format
                        check_num = fields[index_transaction_check_num]

                        # There is a check in the CU DATABASE with number '1'.
                        # We're renumbering it for the DATABASE
                        if check_num == '1':
                            check_num = '999999'

                        # The check info resides in the checks table. The 'main' entry for the check has
                        # no useful budget information.
                        desc = 'Check'
                        budget_category_dict[0] = ['XXX', 0, '']

                    # If the record is not a check, fill in the budget info from the payee DATABASE or
                    # optional extra budget fields
                    else:
                        # Lookup the default budget category from the payee DATABASE

                        # defaults to 'UNKNOWN'
                        bud_cat = self.lookup_payee_category(transaction_payee, trans_date)

                        # set the default budget date and amount from the transaction date and amount
                        bud_amt = fields[index_transaction_amount]

                        # process the extra budget fields which may mean extra DATABASE records
                        budget_category_dict = self.process_budget_fields(fields[expected_fields:],
                                                                          bud_amt, bud_cat, trans_date,
                                                                          tid)
                        

                    # end if

                    self.insert_entry_into_dict(
                        budget_category_dict,
                        tid,
                        trans_date,
                        desc if check_num else ' '.join(transaction_payee.split()) if transaction_payee
                        else fields[index_payee],
                        check_num,
                        'b',
                        fields[index_transaction_amount],
                        comment,
                        output_dict)
                    line_num += 1
                # end if line_num == 0
            # end for each line
        # end with open

        print('readMonthlyCUFile processed', line_num, 'records from ' + file_name + '\n')
        return output_dict

    def read_monthly_amex_file(self, file_name):
        """Read in the downloaded American Express file line-by-line, and insert transactions in a
        dictionary. OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the American Express download file
        :rtype: dict
        """
        line_num = 0
        expected_fields = 5
        output_dict = {}
        with open(file_name) as file_ptr:
            for line in file_ptr:
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clear_commas_in_quotes(' ', line)

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
                if len(field) < expected_fields:
                    print('Missing fields in file {}. Expected at least {} but got {}. Line:'
                          '\n{}'.format(file_name, expected_fields, len(field), line))
                    sys.exit(1)

                # parse the first field -- transaction date
                trans_date = field[0]  # mm/dd/yyyy

                # parse the transaction reference
                trans_ref = field[1].split()[1]

                # transaction amount
                trans_amt = field[2]

                # transaction payee
                trans_payee = field[3]

                # Lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # process the extra budget fields which may mean extra DATABASE
                # records
                budget_category_dict = self.process_budget_fields(field[expected_fields:], trans_amt,
                                                                  bud_cat, trans_date, trans_ref)

                # insert the record(s) into the dictionary
                self.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date, trans_payee,
                                            '', 'x', trans_amt, comment, output_dict)
                line_num += 1
            # end for
        print('read_monthly_amex_file processed {} records from {}\n'.format(line_num, file_name))
        return output_dict

    def read_monthly_citi_file(self, file_name):
        """Read in the downloaded Citibank file line-by-line, and insert transactions in a dictionary.
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Citibank download file
        :rtype: dict
        """
        '''
        Citi Card took over all Costco American Express card accounts on June 3, 2016. Citi has all
        historical Costco AMEX card transactions back to May 2014, if needed.  But those Amex-era
        download formats will be in the earlier Citi download format, not the former Amex format.

        On or before 06/02/2016:
            0                     1                   2                                                       3               4             5
        "Status",               "Date",         "Description",                                              "Debit",       "Credit",   "Member Name"
        "Cleared",           "06/02/2016",       "E 470 EXPRESS TOLLS                     ",               "32.55",           "",      "CHRIS ANDERSON"

        On or after 06/03/2016 ('new_format'):
            0                     1                   2                                                       3               4             5
        "Status",               "Date",         "Description",                                              "Debit",       "Credit",   "Member Name"
        "Cleared",           "06/03/2016",       "AMAZON.COM                           XXXX-XXXX-XXXX-3003","8.65",           "",      "KATHY ANDERSON"

            0                     1                   2                                                        3               4
        "Status",               "Date",         "Description",                                              "Debit",       "Credit"
        "Cleared",           "11/30/2016",      "KING SOOPERS #0729 FUEL  ERIE         CO",                    "",          "22.88"


        The only difference between the two formats is very small: The earlier format does not have the
        crypto-card number at the end of the description fields.
        Both Debit and Credit values are positive.

        TODO: Talk to Citi about adding transaction reference fields to download file
        DONE: Talked to Citi about adding transaction ID fields. They have passed the request on to their
        tech guys.
        '''

        line_num = 0
        expected_fields = 6
        output_dict = {}
        with open(file_name) as file_ptr:
            line = file_ptr.readline()
            while line:
                # Check for normal end-of-line characters. If not, read the next line and join together.
                if ord(line[-2]) != 13 and ord(line[-1]) == 10:
                    # print('Jacked line: "{}" {}-{}'.format(line, ord(line[-2]), ord(line[-1])))
                    line2 = file_ptr.readline()  # read in the next line
                    line = line[:-1] + line2  # strip off last char of first line and join 2nd line to it.
                    print('\nJoined: {}'.format(line.strip()))
                else:
                    print('\nNormal: {}'.format(line.strip()))

                # strip all leading and trailing spaces and new-lines
                line = line.rstrip().lstrip()

                # ignore blank lines
                if not line:
                    line = file_ptr.readline()
                    continue

                # Clear any commas inside quoted fields
                line = self.clear_commas_in_quotes('', line)

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
                fields = line.split(',')

                # skip if it's the header line
                if 'status' in fields[0].lower():
                    line = file_ptr.readline()
                    continue

                # Skip if it's a pending transaction. Sometimes transaction details change when they
                # transition from Pending to Cleared and a slightly different form of the exact same
                # transaction is created and inserted into the DATABASE the next time the Citi
                # transaction file is downloaded and processed by this script, creating a double entry.
                # To prevent this, only consider Cleared transactions which by assumption do not change
                # over time.
                if 'pending' in fields[0].lower():
                    line = file_ptr.readline()
                    continue

                # verify there are no FEWER than the expected number of fields (can be greater)
                if len(fields) < expected_fields:
                    print('Missing fields in file {}. Expected at least {} '
                          'but got {}. Line:\n{}'.format(file_name, expected_fields, len(fields), line))
                    sys.exit(1)

                # parse the second fields -- transaction date
                trans_date = fields[1]  # mm/dd/yyyy
                trans_date_obj = datetime.datetime.strptime(trans_date, "%m/%d/%Y").date()
                new_format = False

                # all dates > 6/2/2016 are new_format
                if trans_date_obj > datetime.datetime.strptime('6/2/2016', '%m/%d/%Y').date():
                    new_format = True

                # transaction amount (fields 3 and 4 are mutually exclusive:
                # one or the other has a value, not both)
                if fields[3]:
                    trans_amt = '-'+fields[3]  # Debits need to be negative value
                else:
                    trans_amt = fields[4]

                # transaction payee
                trans_payee = fields[2]

                # strip-off optional credit card number at end of fields
                if new_format:
                    # strip off crypto-card-number
                    trans_payee = trans_payee[0:37]

                # strip off any and all trailing white-space
                trans_payee = trans_payee.rstrip()

                # Lookup the default budget category from the payee DATABASE defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # TEMP: create a transaction reference from the value of each fields. Empty fields get a
                # value
                hash_key = trans_date+trans_amt+trans_payee+fields[5]
                trans_ref = hashlib.md5(hash_key).hexdigest()
                print(hash_key+' => '+trans_ref)

                # process the extra budget fields which may mean extra DATABASE records
                budget_category_dict = self.process_budget_fields(fields[expected_fields:], trans_amt,
                                                                  bud_cat, trans_date, trans_ref)

                # insert the record(s) into the dictionary
                self.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date, trans_payee,
                                            '', 'C', trans_amt, comment, output_dict)
                line_num += 1
                line = file_ptr.readline()
            # end while
        print('read_monthly_citi_file processed {} records from {}\n'.format(line_num, file_name))
        return output_dict

    def read_monthly_discover_file(self, file_name, download=False):
        """Read in the downloaded Discover Card file line-by-line, and insert transactions in a
        dictionary.
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Discover Card download file
        :param bool download: whether or not to use different transaction date format
        :rtype: dict
        """
        '''
        There are two formats for Discover files, one for downloads, and the other for legacy monthly
        files
        '''
        #      0-2       3-5                6                                                          7        8
        # 2012,08,07,2012,08,07,PANANG THAI CUISINE LAFAYETTE CO,                                     -26,   Restaurants
        # 2007,10,16,2007,10,16,SAFEWAY STORE 1552 FORT COLLINS CO CASHOVER $ 20.00 PURCHASES $ 14.47,-34.47,Supermarkets
        #    tdate      xxxx              tpayee                                                       trans_amt_float  payee type
        #
        # example download file (note date format change and quotation marks):
        #      0         1                  2                                 3       4
        # 07/07/2015,07/07/2015,"MT RUSHMORE KOA/PALMER HILL CITY SD00797R",62.24,"Services"
        #    tdate                        tpayee                            trans_amt_float  payee type
        #
        # Discover card is the only one that does not use a unique identifier for every transaction. We
        # have to create one that is not fool-proof: combine the 2 dates, payee, amount, and payee type
        # with all the spaces removed. Most of the time the resulting string is unique. But once in a
        # while two or more transactions occur on the same day to the same payee for the same amount and
        # then they have to be distinguished. This is problematic.

        line_num = 0
        expected_fields = 5 if download else 9
        check_dict = {}
        output_dict = {}
        with open(file_name) as file_ptr:
            for line in file_ptr:
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines
                if line.startswith('<!--'):
                    print('read_monthly_discover_file: Skipping line "'+line+'"')
                    continue

                # download files have header line; legacy monthly files do not
                if line_num == 0 and download:
                    # This is the file when there are no transactions in the given period
                    if line.startswith('There are no statements'):
                        return output_dict

                    fields = line.split(',')
                    if len(fields) != expected_fields:
                        print('Discover download file header line has {} field(s) instead of expected '
                              '{}'.format(len(fields), expected_fields))
                        sys.exit(1)
                    line_num += 1
                    continue
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clear_commas_in_quotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is guaranteed that there are no
                # extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expected_fields:
                    print('Missing fields in file {}. Expected at least {} but got {}. Line:\n{}'
                          .format(file_name, expected_fields, len(field), line))
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
                    trans_amt_float = float(field[3])
                    trans_amt_string = '%.2f' % -trans_amt_float
                else:
                    trans_amt_float = float(field[7])
                    trans_amt_string = '%.2f' % trans_amt_float

                    # this converts amounts like '-7.1' to a consistent '-7.10'
                    field[7] = trans_amt_string

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
                                         trans_amt_string,
                                         field[4].replace(' ', '')])
                else:
                    # The reference will be the entire line stripped of commas and spaces, minus any
                    # extra fields
                    trans_ref = ''.join(field[:expected_fields]).replace(' ', '')

                # check_dict is here to make sure the record reference is unique
                while trans_ref in check_dict:
                    print('Discover transaction reference "{}" is not unique. Appending "x" to '
                          'it'.format(trans_ref))
                    # If it's already being used, add a character to it
                    trans_ref = trans_ref + 'x'

                # now the reference is unique and can be inserted into the DATABASE
                check_dict[trans_ref] = 0

                # transaction payee
                if download:
                    trans_payee = field[2]
                else:
                    trans_payee = field[6]

                # Lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # process the extra budget fields which may mean extra DATABASE records
                budget_category_dict = self.process_budget_fields(field[expected_fields:],
                                                                  trans_amt_string, bud_cat, trans_date,
                                                                  trans_ref)

                # insert the record(s) into the dictionary
                self.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date, trans_payee,
                                            '', 'd', trans_amt_string, comment, output_dict)
                line_num += 1
            # end for
        print('read_monthly_discover_file processed {} records from {}\n'.format(line_num, file_name))
        return output_dict

    def read_monthly_chase_file(self, file_name):
        """Read in the downloaded Chase Bank file line-by-line, and insert transactions in a dictionary.
        OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Chase Bank download file
        :rtype: dict
        """
        '''
          0            1                                     2                                       3
        CREDIT,20100216120000[0:GMT],"Online Transfer from  MMA XXXXXX6306 transaction#: 313944149",19.79
        DEBIT,20100212120000[0:GMT],"MCDONALD'S F109 BOULDER         02/11MCDONALD'",              -1.08
        CHECK,20100216120000[0:GMT],"CHECK 1108",                                                  -90.00
        trtype       tdatetime                           payee                                      tamt
        '''

        line_num = 0
        expected_fields = 4
        output_dict = dict()
        with open(file_name) as file_ptr:
            for line in file_ptr:
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clear_commas_in_quotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is guaranteed that there are no
                # extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expected_fields:
                    print('Missing fields in file {}. Expected at least {} but got {}. Line:\n{}'
                          .format(file_name, expected_fields, len(field), line))
                    sys.exit(1)

                # parse the date field -- transaction date
                trans_date = field[1][4:6]+'/'+field[1][6:8]+'/'+field[1][0:4]

                # parse the transaction reference
                # The reference will be the entire line stripped of commas and spaces
                trans_ref = line.replace(',', '').replace(' ', '')

                # transaction amount
                trans_amt = field[3]

                # transaction payee
                # strip out extra spaces
                trans_payee = ' '.join(field[2].split())

                # Lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # process the extra budget fields which may mean extra DATABASE
                # records
                budget_category_dict = self.process_budget_fields(field[expected_fields:], trans_amt,
                                                                  bud_cat, trans_date, trans_ref)

                # insert the record(s) into the dictionary
                self.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date, trans_payee,
                                            '', 'c', trans_amt, comment, output_dict)
                line_num += 1
            # end for
        print('read_monthly_chase_file processed {} records from {}\n'.format(line_num, file_name))
        return output_dict

    def read_download_barclay_file(self, file_name):
        """Read in the downloaded Barclay Card file line-by-line, and insert transactions in a
        dictionary. OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Barclay Card download file
        :rtype: dict
        """
        # This is the download file format:
        #
        # ...<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20150203050000.000<DTUSER>20150203050000.000<TRNAMT>566.64<FITID>75140215034020315130448108<NAME>PAYMENT RECV'D CHECKFREE</STMTTRN>...
        #
        line_num = 0
        output_dict = dict()
        with open(file_name) as file_ptr:
            for line in file_ptr:
                if '<STMTTRN>' in line:
                    transactions = line.split('<STMTTRN>')
                    # for each transaction (element 0 does not contain what we are looking for)
                    for trans in transactions[1:]:
                        if not '<DTPOSTED>' in trans or \
                                not '<TRNAMT>' in trans or \
                                not '<FITID>' in trans or \
                                not '<NAME>' in trans:
                            print('Missing fields in file {}. Expected 4 fields, but one or more '
                                  'are missing: {}'.format(file_name, trans))
                            sys.exit(1)
                        match_obj = re.search(r'<FITID>([^<]+)<', trans)
                        if match_obj:
                            trans_ref = match_obj.group(1)
                        else:
                            print('Error matching <FITID> in transaction "{}" in file '
                                  '{}'.format(trans, file_name))
                            sys.exit(1)
                        match_obj = re.search(r'<DTPOSTED>([^<]+)<', trans)
                        if match_obj:
                            trans_date = (match_obj.group(1)[4:6]
                                          + '/' +
                                          match_obj.group(1)[6:8]
                                          + '/' +
                                          match_obj.group(1)[:4])
                        else:
                            print('Error matching <DTPOSTED> in transaction "{}" in file {}'
                                  .format(trans, file_name))
                            sys.exit(1)
                        match_obj = re.search(r'<TRNAMT>([^<]+)<', trans)
                        if match_obj:
                            trans_amt = match_obj.group(1)
                        else:
                            print('Error matching <TRNAMT> in transaction "{}" in file {}'
                                  .format(trans, file_name))
                            sys.exit(1)
                        match_obj = re.search(r'<NAME>([^<]+)<', trans)
                        if match_obj:
                            trans_payee = match_obj.group(1)
                        else:
                            print('Error matching <NAME> in transaction "{}" in file {}'
                                  .format(trans, file_name))
                            sys.exit(1)

                        # lookup the default budget category from the payee DATABASE
                        # defaults to 'UNKNOWN'
                        bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                        # set the default budget date and amount from the transaction date and amount
                        bud_date = trans_date
                        bud_amt = trans_amt

                        # insert the record(s) into the dictionary
                        budget_category_dict = dict()
                        budget_category_dict[0] = [bud_cat, bud_amt, bud_date]
                        self.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date,
                                                    trans_payee, '', 'y', trans_amt, '', output_dict)
                        line_num += 1
                    # end for each transaction
                # end if <STMTTRN> found in line
            # end for each line in file
        print('read_download_barclay_file processed {} records from {}\n'.format(line_num, file_name))
        return output_dict

    def read_monthly_barclay_file(self, file_name):
        """Read in the downloaded Barclay Card file line-by-line, and insert transactions in a
        dictionary. OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Barclay Card download file
        :rtype: dict
        """
        # This is the monthly file format:
        #   0  1  2             3                      4         5
        # 2011,04,04,252478010910000016899273001,BOMBAY MASALA,31.00
        # tyr tmo tday         tref                  payee      tamt
        line_num = 0
        expected_fields = 6
        output_dict = {}
        with open(file_name) as file_ptr:
            for line in file_ptr:
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines

                # Clear any commas inside quoted fields
                line = self.clear_commas_in_quotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is guaranteed that there are no
                # extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields (can be greater)
                if len(field) < expected_fields:
                    print('Missing fields in file {}. Expected at least {} but got {}. Line:\n'
                          '{}'.format(file_name, expected_fields, len(field), line))
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

                # lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # process the extra budget fields which may mean extra DATABASE records
                budget_category_dict = self.process_budget_fields(field[expected_fields:], trans_amt,
                                                                  bud_cat, trans_date, trans_ref)

                # insert the record(s) into the dictionary
                self.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date, trans_payee,
                                            '', 'y', trans_amt, comment, output_dict)
                line_num += 1
            # end for
        print('read_monthly_barclay_file processed {} records from {}\n'.format(line_num, file_name))
        return output_dict

    def process_file(self, file_name):
        """NOT USED"""
        local_inserted = 0

        if not file_name.endswith('.txt'):
            return
        if file_name.endswith('cat.txt'):
            return
        if file_name.endswith('DB.txt'):
            return
        if '2004' in file_name or '2005' in file_name:
            return
        print('Processing file ' + file_name)
        if 'Discover' in file_name:
            output_dict = self.read_monthly_discover_file('decoded-dbs/' + file_name)
        elif 'Amex' in file_name:
            output_dict = self.read_monthly_amex_file('decoded-dbs/' + file_name)
        elif 'Chase' in file_name:
            output_dict = self.read_monthly_chase_file('decoded-dbs/' + file_name)
        elif 'Barclay' in file_name:
            output_dict = self.read_monthly_barclay_file('decoded-dbs/' + file_name)
        else:
            output_dict = self.read_monthly_cu_file('decoded-dbs/' + file_name)

        for key, val in output_dict.iteritems():
            record = ('INSERT into main ('
                      'tran_date, '
                      'tran_ID, '
                      'tran_desc, '
                      'tran_checknum, '
                      'tran_type,'
                      'tran_amount, '
                      'bud_category, '
                      'bud_amount, '
                      'bud_date, '
                      'comment) '
                      'VALUES ('
                      'STR_TO_DATE("'+val[0]+'","%m/%d/%Y"), "'
                      + key+'", "'
                      + val[2] + '", "'
                      + val[3] + '", "'
                      + val[4] + '", "'
                      + val[5] + '", "'
                      + val[6] + '", "'
                      + val[7] + '", '
                      'STR_TO_DATE("'+val[8]+'","%m/%d/%Y"), "'
                      + val[9] + '");')
            self.cur.execute(record)
            local_inserted += 1

        print('Inserted', local_inserted, 'records into DATABASE')
        self.inserted += local_inserted
        self.total_files += 1
        self.files_processed += 1

        return

    def merge_over_the_counter_checks(self):
        """NOT USED"""
        for file_name in glob.glob('decoded-dbs/*.txt'):
            if '2004' in file_name or '2005' in file_name:
                continue
            if 'Discover' in file_name:
                continue
            if 'Amex' in file_name:
                continue
            if 'Chase' in file_name:
                continue
            if 'Barclay' in file_name:
                continue
            if file_name.endswith('cat.txt'):
                continue
            if file_name.endswith('DB.txt'):
                continue

            # We are left with credit union files
            output_dict = self.read_monthly_cu_file(file_name)
            for key, val in output_dict.iteritems():
                if val[3].strip():  # Check number is not empty
                    self.cur.execute("select tran_checknum from main where tran_ID = '"+key+"';")
                    self.cur.fetchone()
                    for row in self.cur:
                        # Check number field does not exist in DATABASE for this transaction
                        if row[0] == 0:
                            query = ("update main set tran_checknum = '"+val[3]+"',tran_desc = '"
                                     + val[2] + "' where tran_ID = '" + key + "';")
                            print(query)
                            self.cur.execute(query)
