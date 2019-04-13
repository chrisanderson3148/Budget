"""Module contains methods to etc"""

from __future__ import print_function
import re
import datetime
import glob
import json
from warnings import filterwarnings
import pprint
import MySQLdb
import transfer_cu_files
import transfer_amex_files
import transfer_citi_files
import transfer_discover_files
import transfer_chase_files
import transfer_barclay_files
from transferPayee import TransferPayee

filterwarnings('ignore', category=MySQLdb.Warning)

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


class TransferMonthlyFilesToDB(transfer_barclay_files.Mixin, transfer_chase_files.Mixin,
                               transfer_discover_files.Mixin, transfer_citi_files.Mixin,
                               transfer_amex_files.Mixin, transfer_cu_files.Mixin, object):
    """Class to transfer monthly files to DATABASE

    :param Any cursor: the DATABASE CURSOR object
    """

    DEFAULT_BUDGET_CATEGORY = 'UNKNOWN'

    def __init__(self, cursor, logger):
        self.cur = cursor
        self.logger = logger
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

    def pretty(self, the_dict, indent=0):
        """Recursively prints the elements of the given dictionary

        NEVER CALLED

        :param dict the_dict: the dictionary to print
        :param int indent: the number of spaces to indent each new level (default = 0)
        """
        for key, value in the_dict.iteritems():
            # if indent == 0: print '\n'
            self.logger.log('  ' * indent + str(key))
            if isinstance(value, dict):
                self.pretty(value, indent+1)
            else:
                self.logger.log('  ' * (indent + 1) + str(value))

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
                self.logger.log('Payee "{}" match "{}" with category "{}"'.format(payee, key, category))
                return category

        self.logger.log('No payroll/ignore/transfer match found in "{}"'.format(payee))
        if 'transfer' in payee.lower():
            return 'TRANSFER'

        #
        # If not a standard, hard-coded budget category, try looking up in the payee DATABASE dictionary
        for key in sorted(self.payee_dict):
            match_object = re.match(self.payee_dict[key][0], payee, re.I)
            if match_object:
                cats = self.payee_dict[key][1].split(';')
                if len(cats) == 1:
                    self.logger.log('Payee "{}" match "{}" with category "{}"'.
                                    format(payee, self.payee_dict[key][0], cats[0]))
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
        self.logger.log('Payee "' + payee + '" no match found')
        return self.DEFAULT_BUDGET_CATEGORY

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
        self.logger.log('Processing file ' + file_name)
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

        self.logger.log('Inserted', local_inserted, 'records into DATABASE')
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
                            self.logger.log(query)
                            self.cur.execute(query)
