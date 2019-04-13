#!/usr/bin/python2

from __future__ import print_function
import sys
import os
import traceback
import MySQLdb
import transferCheckUtils
from utils import Logger
from transferFilesToDB import TransferMonthlyFilesToDB


class ProcessDownloads(object):
    CU_FILE = 'downloads/ExportedTransactions.csv'
    CK_FILE = 'downloads/checks'
    DI_FILE = 'downloads/Discover-RecentActivity.csv'
    CI_FILE = 'downloads/Citi-RecentActivity.csv'
    DO_INSERT = True  # set to True to actually insert into DATABASE

    def __init__(self):
        self.logger = Logger('process_download_log', append=True, print_to_console=True)

        # Verify symbolic link to 'downloads' is not broken
        if os.path.isdir('downloads'):
            if os.path.islink('downloads') and not os.path.exists(os.readlink('downloads')):
                self.logger.log('The folder "downloads" is a symbolic link, but its target does not '
                                'exist.')
                self.logger.log('To restore it as a symbolic link, re-install vmware-tools:')
                self.logger.log('1. cd /home/chrisanderson/Desktop/vmware-tools-distrib')
                self.logger.log('2. "sudo perl vmware-install.pl" and enter password for chrisanderson')
                self.logger.log('3. Answer all questions with the default (just hit <return>)')
                sys.exit(1)

        # Verify all downloads files exist
        all_exist = True
        for download_file in [self.CU_FILE, self.CK_FILE, self.DI_FILE, self.CI_FILE]:
            if not os.path.exists(download_file):
                self.logger.log('Download file "' + download_file + '" does not exist')
                all_exist = False
        if not all_exist:
            sys.exit(1)

        self.records_inserted = 0

        # Open a connection to the DATABASE
        self.db = MySQLdb.connect(host='localhost', user='root', passwd='sawtooth', db='officialBudget')
        self.CURSOR1 = self.db.cursor()
        self.CURSOR2 = self.db.cursor()

    def execute(self):
        # store the list of main DB keys for quick searching
        query_str = 'SELECT tran_ID from main;'
        try:
            self.CURSOR1.execute(query_str)
        except MySQLdb.Error:
            (exception_type, value, tb) = sys.exc_info()
            self.logger.log('Main(): Exception executing query: ' + query_str)
            self.global_exception_printer(exception_type, value, tb)
            sys.exit(1)

        db_keys = set()
        for row in self.CURSOR1:
            db_keys.add(row[0])

        query = 'SELECT tnum from checks;'
        try:
            self.CURSOR1.execute(query)
        except MySQLdb.Error:
            (exception_type, value, tb) = sys.exc_info()
            self.logger.log('Main(): Exception executing query: ' + query)
            self.global_exception_printer(exception_type, value, tb)
            sys.exit(1)

        ck_keys = set()
        for row in self.CURSOR1:
            ck_keys.add(row[0])

        transfer = TransferMonthlyFilesToDB(self.CURSOR1, self.logger)

        # handle credit union transactions including checks
        if os.path.isfile(self.CK_FILE):  # process checks first
            self.logger.log('\nprocessing credit union checks download file...')
            t_dict = transferCheckUtils.read_checks_file(self.CK_FILE)
            self.insert_dict_into_checks_db(t_dict, ck_keys)

        if os.path.isfile(self.CU_FILE):  # process cleared transactions second
            self.logger.log('\nprocessing credit union download file...')
            t_dict = transfer.read_monthly_cu_file(self.CU_FILE)
            self.insert_dict_into_main_db(t_dict, db_keys)

        self.clear_cu_checks()  # mark cleared checks

        # if os.path.isfile(AX_FILE):
        #     self.my_log.log('\nprocessing American Express download file...')
        #     t_dict = TF.read_monthly_amex_file(AX_FILE)
        #     self.insert_dict_into_main_db(t_dict, db_keys)

        if os.path.isfile(self.CI_FILE):
            self.logger.log('\nprocessing CitiCard download file...')
            t_dict = transfer.read_monthly_citi_file(self.CI_FILE)
            self.insert_dict_into_main_db(t_dict, db_keys)

        if os.path.isfile(self.DI_FILE):
            self.logger.log('\nprocessing Discover download file...')

            # process a download file, not a monthly file
            t_dict = transfer.read_monthly_discover_file(self.DI_FILE, True)
            self.insert_dict_into_main_db(t_dict, db_keys)

        # if os.path.isfile(self.BY_FILE):
        #     self.my_log.log('\nprocessing Barclay download file...')
        #     t_dict = TF.read_download_barclay_file(self.BY_FILE)
        #     self.insert_dict_into_main_db(t_dict, db_keys)

        self.logger.log('\n' + ('Inserted ' if self.DO_INSERT else 'Did not insert ') +
                        str(self.records_inserted) + ' records into DB')

    def __del__(self):
        self.print_uncleared_checks()
        self.print_unrecorded_checks()
        self.print_unknown_non_check_transactions()

    def global_exception_printer(self, e_type, val, trace_back):
        """Prints exceptions that are caught globally, ie, uncaught elsewhere

        :param types.ExceptionType e_type: the caught exception type
        :param int val: the exception value
        :param Any trace_back: the exception traceback object
        """
        trs = ''
        for my_trace_back in traceback.format_list(traceback.extract_tb(trace_back)):
            trs += my_trace_back
        self.logger.log('**********************************\nException occurred\nType: ' + str(e_type) +
                        '\nValue: ' + str(val) + '\nTraceback:\n' + trs +
                        '*********************************')

    def clear_cu_checks(self):
        """Runs query to identify main table check entries and attempt to clear them"""
        updated = 0
        local_query = ('select tran_checknum,tran_date from main where tran_checknum != "0" and '
                       'tran_type = "b";')
        try:
            self.CURSOR1.execute(local_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            self.logger.log('clearCUChecks(): Exception executing query: ' + local_query)
            self.global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        for inner_row in self.CURSOR1:
            check_num = str(inner_row[0])
            transaction_date = inner_row[1]

            local_query = ('update checks set clear_date = "' +
                           str(transaction_date) +
                           '" where tchecknum = "' + check_num+'";')
            try:
                self.CURSOR2.execute(local_query)
            except MySQLdb.Error:
                (my_exception_type, my_value, my_tb) = sys.exc_info()
                self.logger.log('clearCUChecks(): Exception executing query: ' + local_query)
                self.global_exception_printer(my_exception_type, my_value, my_tb)
                sys.exit(1)

            updated += 1
        self.db.commit()
        self.logger.log('Updated {} checks in checks DATABASE'.format(updated))

    def print_unknown_non_check_transactions(self):
        """Print a list of unknown, non-check transactions"""
        self.logger.log('\nNon-check transactions marked "UNKNOWN" since 1/1/2006:')
        self.logger.log('%-12s %-40s %10s' % ("Tran date", "Description", "Amount"))

        my_query = ('select tran_date,tran_desc,tran_amount from main where bud_category = "UNKNOWN" '
                    'and tran_date > "2005-12-31" and tran_desc not like "CHECK%" and tran_desc not '
                    'like "Check%" order by tran_date;')
        try:
            self.CURSOR1.execute(my_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            self.logger.log('print_unknown_non_check_transactions(): Exception executing query: ' +
                            my_query)
            self.global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        amount = 0
        for inner_row in self.CURSOR1:
            self.logger.log('%-12s %-40s $%10.2f' % (inner_row[0].strftime('%m/%d/%Y'),
                                                     inner_row[1][:40], inner_row[2]))
            amount += inner_row[2]
        self.logger.log('-----------------------------------------------------------------')
        self.logger.log('%-53s $%10.2f' % ('Total:', amount))

    def print_unrecorded_checks(self):
        """Print a list of unrecorded checks"""
        self.logger.log('\nCleared, unrecorded checks: ')
        self.logger.log('%-5s %-12s %8s' % ("CNum", "Cleared date", "Amount"))

        my_query = ('select tran_checknum,tran_date,tran_amount from main where tran_checknum != "0" and'
                    ' tran_type = "b";')
        try:
            self.CURSOR1.execute(my_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            self.logger.log('print_unrecorded_checks(): Exception executing query: ' + my_query)
            self.global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        # for every cleared CU check, see if it also exists as a transaction in
        # the checks DATABASE, with at least an amount
        for inner_row in self.CURSOR1:
            my_query = ('select tchecknum from checks where tchecknum = "'+str(inner_row[0])
                        + '" and tamt is not null;')
            try:
                self.CURSOR2.execute(my_query)
            except MySQLdb.Error:
                (my_exception_type, my_value, my_tb) = sys.exc_info()
                self.logger.log('print_unrecorded_checks(): Exception executing query: ' + my_query)
                self.global_exception_printer(my_exception_type, my_value, my_tb)
                sys.exit(1)

            if self.CURSOR2.rowcount == 0:
                self.logger.log('%-5d %-12s $%7.2f' % (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                                                       abs(inner_row[2])))

    def print_uncleared_checks(self):
        """Print a list of uncleared checks"""
        my_dict = dict()
        self.logger.log('\nUncleared checks since 1/1/2006: ')
        self.logger.log('%-5s %-10s %8s %-30s %s' % ("CNum", "Date", "Amt", "Payee", "Comments"))

        my_query = ('select tnum,tdate,tamt,tpayee,comments from checks where clear_date is null and '
                    'tdate > "2005-12-31" and tamt != 0.0 order by tnum;')
        try:
            # uncleared checks have no cleared date, transacted in 2006 or later, and have an amount (not
            # cancelled)
            self.CURSOR1.execute(my_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            self.logger.log('print_uncleared_checks(): Exception executing query: ' + my_query)
            self.global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        for inner_row in self.CURSOR1:
            key = (str(inner_row[1])+inner_row[0]+str(abs(inner_row[2]))+inner_row[3]+inner_row[4])
            my_dict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                            (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                             abs(inner_row[2]), inner_row[3], inner_row[4]))

        my_query = ('select tnum,tdate,tamt,tpayee,comments from chasechecks where clear_date is null '
                    'and tdate > "2005-12-31" and tamt != 0.0  order by tnum;')
        try:
            self.CURSOR1.execute(my_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            self.logger.log('print_uncleared_checks(): Exception executing query: ' + my_query)
            self.global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        for inner_row in self.CURSOR1:
            key = (str(inner_row[1]) + inner_row[0] + str(abs(inner_row[2])) + inner_row[3] +
                   inner_row[4])
            my_dict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                            (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                             abs(inner_row[2]), inner_row[3], inner_row[4]))
        for entry in sorted(my_dict):
            self.logger.log(my_dict[entry])

    def insert_dict_into_checks_db(self, download_dict, keys_set):
        """Insert checks in downloadDict into the checks DATABASE

        The records in the downloadDict have all been processed so that bud_cat, bud_amt, and bud_date are
        filled in.

        :param dict download_dict: the records to insert
        :param set keys_set: Later
        """
        for key, val in download_dict.iteritems():
            # existing record found -- ignore
            if key in keys_set or key + '-0' in keys_set:
                continue

            # downloaded record is new and does not exist in the checks DATABASE
            # key, checknum, amt, date, payee, bud[0], bud[1], bud[2], comment
            #         0       1    2      3     4cat     5amt   6date     7
            my_query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_date,'
                        'comments) values ("'+val[0]+'","'+val[0]+'","'+val[1]+'","STR_TO_DATE("'
                        + val[2]+'","%m/%d/%Y"),"'+val[3]+'","'+val[4]+'","'+val[5]+'",STR_TO_DATE("'
                        + val[6]+'","%m/%d/%Y"),"'+val[7] + '");')
            # If inserting is enabled, insert into DATABASE
            if self.DO_INSERT:
                try:
                    self.CURSOR1.execute(my_query)
                except MySQLdb.Error:
                    (my_exception_type, my_value, my_tb) = sys.exc_info()
                    self.logger.log('insert_dict_into_checks_db(): Exception executing query: ' + my_query)
                    self.global_exception_printer(my_exception_type, my_value, my_tb)
                    sys.exit(1)

            self.logger.log('Key {} is not in "checks" DATABASE -- {}'.
                            format(key, ('' if self.DO_INSERT else 'would have ') + 'inserted'))
            self.records_inserted += 1

    def insert_dict_into_main_db(self, download_dict, keys_set):
        """Insert records from downloadDict into the main table

        :param dict download_dict:
        :param set keys_set:
        """
        for key, val in download_dict.iteritems():
            if '|' in key:
                old_key = key.split('|')[0]
                new_key = key.split('|')[1]
            else:
                old_key = key
                new_key = key

            # don't insert existing records into DATABASE, but check if should
            # UPDATE the existing record
            if old_key in keys_set or old_key + '-0' in keys_set or new_key in keys_set or new_key \
                    + '-0' in keys_set:
                continue

            # For downloaded transactions whose key does not exist in the database, do one last
            # check for possible duplicates: same transaction date, amount, and description.
            # The credit union transactions downloads sometimes come back with different transaction IDs
            # for the same transactions downloaded at different times. Without this check, they
            # will get inserted into the database as duplicate transactions and cause problems that are
            # hard to clean up later.
            # Check with the user if the record should be inserted anyway. If not, don't insert it.
            check_query = ('SELECT tran_ID,tran_date,tran_desc,tran_checknum,tran_amount from main '
                           'where tran_date=STR_TO_DATE("' + val[0] + '","%m/%d/%Y") and tran_desc="' +
                           val[2] + '" and tran_amount="' + val[5] + '" and tran_checknum="' +
                           val[3] + '";')
            try:
                self.CURSOR1.execute(check_query)
            except MySQLdb.Error:
                (my_exception_type, my_value, my_tb) = sys.exc_info()
                self.logger.log('insert_dict_into_main_db(): Exception executing query: {}'.
                                format(check_query))
                self.global_exception_printer(my_exception_type, my_value, my_tb)
                sys.exit(1)

            #
            # One match - insert or ignore new record, or replace existing record with it.
            #
            if self.CURSOR1.rowcount == 1:
                self.logger.log('Possible duplicate record with different transaction ID (existing '
                                'record VS candidate record):')
                existing_record_key = ''
                for row in self.CURSOR1:
                    existing_record_key = row[0]
                    self.logger.log('old "{}" "{}" "{}" "{}" "{}" VS new "{}" "{}" "{}" "{}" "{}"'.
                                    format(row[0], row[1], row[2], row[3], row[4], new_key, val[0],
                                           val[2], (val[3] if val[3] else "0"), val[5]))
                response = raw_input("What to do with this record: [insert|ignore|replace (existing)]? ")
                self.logger.log('response="{}"'.format(response))
                if response.lower().startswith('ignore'):
                    continue  # do NOT insert this record!!
                if response.lower().startswith('replace'):  # delete existing record first
                    delete_query = 'DELETE FROM main where tran_id = "{}";'.format(existing_record_key)
                    try:
                        # delete existing record from database (first part of replacing with new record)
                        self.CURSOR2.execute(delete_query)
                    except MySQLdb.Error:
                        (my_exception_type, my_value, my_tb) = sys.exc_info()
                        self.logger.log('insert_dict_into_main_db(): Exception executing query: ' +
                                        delete_query)
                        self.global_exception_printer(my_exception_type, my_value, my_tb)
                        sys.exit(1)
                        # otherwise, keep going and insert it

            #
            # More than one match - insert or ignore new record, no replace
            #
            elif self.CURSOR1.rowcount > 1:
                self.logger.log('Possible duplicate records with different transaction IDs (existing '
                                'record VS candidate records):')
                for row in self.CURSOR1:
                    self.logger.log('Existing record: "{}" "{}" "{}" "{}" "{}"\nNew record:      '
                                    '"{}" "{}" "{}" "{}" "{}"'.
                                    format(row[0], row[1], row[2], row[3], row[4], new_key, val[0],
                                           val[2], (val[3] if val[3] else "0"), val[5]))
                response = raw_input("Insert or ignore new record [insert|ignore]? ")
                if response.lower().startswith('ignore'):
                    continue  # do NOT insert the record
                    # otherwise keep going and insert it

            # It seems to check out -- insert into the database
            my_query = ('INSERT into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,'
                        'tran_amount,bud_category,bud_amount,bud_date,comment) VALUES '
                        '(STR_TO_DATE("' + val[0] + '","%m/%d/%Y"), "' + new_key+'", "' + val[2]+'", "' +
                        (val[3] if val[3] else "0") + '", "' + val[4] + '", "' + val[5] + '", "' +
                        val[6] + '", "' + str(val[7]) + '", STR_TO_DATE("' +
                        (val[8] if len(val[8]) else val[0]) + '","%m/%d/%Y"), "' + val[9] + '");')

            # If inserting is enabled, insert into the appropriate DATABASE
            if self.DO_INSERT:
                try:
                    self.CURSOR1.execute(my_query)
                except MySQLdb.Error:
                    (my_exception_type, my_value, my_tb) = sys.exc_info()
                    self.logger.log('insert_dict_into_main_db(): Exception executing query: ' + my_query)
                    self.global_exception_printer(my_exception_type, my_value, my_tb)
                    sys.exit(1)
            else:
                val[1] = new_key
                self.logger.log('Key {} is not in "main" DATABASE -- {}inserted {}'.
                                format(new_key, ('' if self.DO_INSERT else 'would have '), val))

            self.records_inserted += 1


#
# MAIN PROGRAM
#

process_downloads = ProcessDownloads()
process_downloads.execute()
