#!/usr/bin/python3

from __future__ import print_function
import sys
import os
import inspect
import traceback
import pymysql
import transfer_cu_files
import transfer_citi_files
import transfer_discover_files
import transferFilesToDB
import transfer_downloads_to_db
import utils
from utils import Logger


class ProcessDownloads(object):
    CU_FILE = 'downloads/ExportedTransactions.csv'
    CK_FILE = 'downloads/checks'
    DI_FILE = 'downloads/Discover-RecentActivity.csv'
    CI_FILE = 'downloads/Citi-RecentActivity.csv'

    def __init__(self, do_insert=True):
        self.logger = Logger('process_download_log', append=True, print_to_console=True)

        # Open a connection to the DATABASE
        self.db = pymysql.connect(host='localhost', user='root', passwd='sawtooth', db='officialBudget')
        self.db_cursor1 = self.db.cursor()
        self.db_cursor2 = self.db.cursor()

        self.records_inserted = 0
        self.DO_INSERT = do_insert

    def _setup(self):
        # Verify symbolic link to 'downloads' is not broken
        # if os.path.isdir('downloads'):
        #     if os.path.islink('downloads') and not os.path.exists(os.readlink('downloads')):
        #         self.logger.log("The folder 'downloads' is a symbolic link, but its target does not exist.")
        #         self.logger.log("To restore it as a symbolic link, re-install vmware-tools:")
        #         self.logger.log("1. cd /home/chrisanderson/Desktop/vmware-tools-distrib")
        #         self.logger.log("2. 'sudo perl vmware-install.pl' and enter password for chrisanderson")
        #         self.logger.log("3. Answer all questions with the default (just hit <return>)")
        #         sys.exit(1)

        # Verify all downloads files exist
        all_exist = True
        for download_file in [self.CU_FILE, self.CK_FILE, self.DI_FILE, self.CI_FILE]:
            if not os.path.exists(download_file):
                self.logger.log(f"Download file '{download_file}' does not exist")
                all_exist = False
        if not all_exist:
            sys.exit(1)

    def __del__(self):
        self.db.close()
        self.logger.log('Shutting down...')

    def execute_cursor1(self, query_string):
        try:
            self.db_cursor1.execute(query_string)
        except pymysql.Error as sqlexc:
            self.logger.log(f"{inspect.stack()[1][3]}(): Exception executing query: {query_string}")
            self.global_exception_printer(f"{sqlexc}")
            sys.exit(1)

    def execute_cursor2(self, query_string):
        try:
            self.db_cursor2.execute(query_string)
        except pymysql.Error as sqlexc:
            # (exception_type, value, tb) = sys.exc_info()
            self.logger.log(f"{inspect.stack()[1][3]}(): Exception executing query: {query_string}")
            self.global_exception_printer(f"{sqlexc}")
            sys.exit(1)

    def execute(self):
        self._setup()

        # store the list of main DB and checks keys for quick searching
        self.execute_cursor1('SELECT tran_ID from main;')
        db_keys = set(row[0] for row in self.db_cursor1)

        self.execute_cursor1('SELECT tnum from checks;')
        ck_keys = set(row[0] for row in self.db_cursor1)

        transfer = transferFilesToDB.TransferMonthlyFilesToDB(self.db_cursor1, self.logger)

        # handle credit union transactions including checks
        # This is archaic.
        # if os.path.isfile(self.CK_FILE):  # process checks first
        #     self.logger.log('\n**** processing credit union checks download file... ****\n')
        #     t_dict = transferCheckUtils.read_checks_file(self.CK_FILE)
        #     self.insert_dict_into_checks_db(t_dict, ck_keys)

        if os.path.isfile(self.DI_FILE):
            self.logger.log('\n**** processing Discover download file... ****\n')
            t_dict_oldway = transfer_discover_files.read_monthly_discover_file(self.DI_FILE, transfer, self.logger)
            # t_dict_newway = transfer_downloads_to_db.convert_downloads_file(
            #     self.DI_FILE, "map_download_to_db.json", "discover_download_format.json", "discover", transfer,
            #     self.logger)
            # if t_dict_newway == t_dict_oldway:
            #     print(f"Discover transfer dicts match")
            # else:
            #     print(f"Discover transfer dicts DO NOT MATCH")
            self.insert_dict_into_main_db(t_dict_oldway, db_keys)

        if os.path.isfile(self.CU_FILE):  # process cleared transactions second
            self.logger.log('\n**** processing credit union download file... ****\n')
            t_dict_oldway = transfer_cu_files.read_monthly_cu_file(self.CU_FILE, transfer, self.logger)
            # t_dict_newway = transfer_downloads_to_db.convert_downloads_file(
            #     self.CU_FILE, "map_download_to_db.json", "cu_download_format.json", "cu", transfer, self.logger)
            # newkeys = list(t_dict_newway.keys())
            # oldkeys = list(t_dict_oldway.keys())
            # assert len(newkeys) == len(oldkeys), f"# keys in new t_dict {len(newkeys)} not equal to old keys {len(oldkeys)}"
            # if newkeys != oldkeys:
            #     for i in range(len(newkeys)):
            #         if newkeys[i] != oldkeys[i]:
            #             print(f"newkey {newkeys[i]} vs {oldkeys[i]}")
            # if t_dict_newway == t_dict_oldway:
            #     print(f"Credit Union transfer dicts match")
            # else:
            #     print(f"Credit Union transfer dicts DO NOT MATCH")
            self.insert_dict_into_main_db(t_dict_oldway, db_keys)

        self.clear_cu_checks()  # mark cleared checks

        if os.path.isfile(self.CI_FILE):
            self.logger.log('\n**** processing CitiCard download file... ****\n')
            t_dict_oldway = transfer_citi_files.read_monthly_citi_file(self.CI_FILE, transfer, self.logger)
            # t_dict_newway = transfer_downloads_to_db.convert_downloads_file(
            #     self.CI_FILE, "map_download_to_db.json", "citi_download_format.json", "citi", transfer, self.logger)
            # if t_dict_newway == t_dict_oldway:
            #     print(f"Citi transfer dicts match")
            # else:
            #     print(f"Citi transfer dicts DO NOT MATCH")
            self.insert_dict_into_main_db(t_dict_oldway, db_keys)

        self.logger.log(f"\n{('Inserted ' if self.DO_INSERT else 'INSERT DISABLED: Would have inserted ')}"
                        f"{self.records_inserted} records into DB")

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
        self.logger.log('**********************************')
        self.logger.log('Exception occurred\nType: {}\nValue: {}\nTraceback:\n{}'.
                        format(e_type, val, trs))
        self.logger.log('**********************************')

    def clear_cu_checks(self):
        """Runs query to identify main table check entries and attempt to clear them"""
        updated = 0
        local_query = ('select tran_checknum,tran_date from main where tran_checknum != "0" and '
                       'tran_type = "b";')
        self.execute_cursor1(local_query)

        for inner_row in self.db_cursor1:
            check_num = str(inner_row[0])
            transaction_date = inner_row[1]

            local_query = ('update checks set clear_date = "{}" where tchecknum = "{}";'.
                           format(transaction_date, check_num))
            self.execute_cursor2(local_query)

            updated += 1
        self.db.commit()
        self.logger.log(f"Updated {updated} checks in checks DATABASE")

    def print_unknown_non_check_transactions(self):
        """Print a list of unknown, non-check transactions"""
        self.logger.log('\nNon-check transactions marked "UNKNOWN" since 1/1/2006:')
        self.logger.log('{:12s} {:40s} {:>11s}'.format("Tran date", "Description", "Amount"))

        my_query = ('select tran_date,tran_desc,tran_amount from main where bud_category = "UNKNOWN" '
                    'and tran_date > "2005-12-31" and tran_desc not like "CHECK%" and tran_desc not '
                    'like "Check%" order by tran_date;')
        self.execute_cursor1(my_query)

        amount = 0
        for inner_row in self.db_cursor1:
            self.logger.log('{:12s} {:40s} ${:>10.2f}'.format(inner_row[0].strftime('%m/%d/%Y'),
                                                              inner_row[1][:40], inner_row[2]))
            amount += inner_row[2]
        self.logger.log('-----------------------------------------------------------------')
        self.logger.log('{:53s} ${:>10.2f}'.format('Total:', amount))

    def print_unrecorded_checks(self):
        """Print a list of unrecorded checks"""
        self.logger.log('\nCleared, unrecorded checks: ')
        self.logger.log('{:5s} {:12s} {:>8s}'.format("CNum", "Cleared date", "Amount"))

        my_query = ('select tran_checknum,tran_date,tran_amount from main where tran_checknum != "0" and'
                    ' tran_type = "b";')
        self.execute_cursor1(my_query)

        # for every cleared CU check, see if it also exists as a transaction in
        # the checks DATABASE, with at least an amount
        for inner_row in self.db_cursor1:
            my_query = ('select tchecknum from checks where tchecknum = "{}" and tamt is not null;'.
                        format(inner_row[0]))
            self.execute_cursor2(my_query)

            if self.db_cursor2.rowcount == 0:
                self.logger.log('{:5d} {:12s} ${:>7.2f}'.format(inner_row[0],
                                                                inner_row[1].strftime('%m/%d/%Y'),
                                                                abs(inner_row[2])))

    def print_uncleared_checks(self):
        """Print a list of uncleared checks"""
        my_dict = dict()
        self.logger.log('\nUncleared checks since 1/1/2006: ')
        self.logger.log('{:5s} {:10s} {:>8s} {:30s} {}'.
                        format("CNum", "Date", "Amt", "Payee", "Comments"))

        my_query = ('select tnum,tdate,tamt,tpayee,comments from checks where clear_date is null and '
                    'tdate > "2005-12-31" and tamt != 0.0 order by tnum;')
        self.execute_cursor1(my_query)

        for inner_row in self.db_cursor1:
            key = (str(inner_row[1])+inner_row[0]+str(abs(inner_row[2]))+inner_row[3]+inner_row[4])
            my_dict[key] = ('{:5s} {:10s} ${:>7.2f} {:30s} {}'.
                            format(inner_row[0], inner_row[1].strftime('%m/%d/%Y'), abs(inner_row[2]),
                                   inner_row[3], inner_row[4]))

        my_query = ('select tnum,tdate,tamt,tpayee,comments from chasechecks where clear_date is null '
                    'and tdate > "2005-12-31" and tamt != 0.0  order by tnum;')
        self.execute_cursor1(my_query)

        for inner_row in self.db_cursor1:
            key = (str(inner_row[1]) + inner_row[0] + str(abs(inner_row[2])) + inner_row[3] +
                   inner_row[4])
            my_dict[key] = ('{:5s} {:10s} ${:>7.2f} {:30s} {}'.
                            format(inner_row[0], inner_row[1].strftime('%m/%d/%Y'), abs(inner_row[2]),
                                   inner_row[3], inner_row[4]))
        for entry in sorted(my_dict):
            self.logger.log(my_dict[entry])

    def insert_dict_into_checks_db(self, download_dict, keys_set):
        """Insert checks in downloadDict into the checks DATABASE

        The records in the downloadDict have all been processed so that bud_cat, bud_amt, and bud_date 
        are filled in.

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
                self.execute_cursor1(my_query)

            self.logger.log('Key {} is not in "checks" DATABASE -- {}'.
                            format(key, ('' if self.DO_INSERT else 'would have ') + 'inserted'))
            self.records_inserted += 1

    def _resolve_possible_duplicate_record(self, new_key, val):
        """Resolve possible duplicate record according to the user's input.
        
        :param str new_key: the transaction ID of the new record
        :param list[any] val: some fields of the existing record
        :returns: whether or not to continue to insert the new record
        :rtype: bool
        """
        self.INSERT = 'insert'
        self.IGNORE = 'ignore'
        self.REPLACE = 'replace'

        num_duplicates = self.db_cursor1.rowcount
        existing_record_key = ''
        for row in self.db_cursor1:
            existing_record_key = row[0]
            self.logger.log('existing record "{}" "{}" "{}" "{}" "{}"'.format(row[0], row[1], row[2],
                                                                              row[3], row[4]))
        self.logger.log('new record "{}" "{}" "{}" "{}" "{}"'.format(new_key, val[0], val[2],
                                                                     (val[3] if val[3] else "0"),
                                                                     val[5]))

        if num_duplicates == 1:
            response = utils.get_valid_response("What to do with possible duplicate record?",
                                                [self.INSERT, self.IGNORE, self.REPLACE])
        else:
            response = utils.get_valid_response("What to do with possible duplicate record?",
                                                [self.INSERT, self.IGNORE])
        self.logger.log(f"response='{response}'")

        # Ignore new record
        if response.lower() == self.IGNORE:
            return False

        # Replace existing record with new record (delete existing record here, insert in caller)
        if response.lower() == self.REPLACE:
            delete_query = f'DELETE FROM main where tran_id = "{existing_record_key}";'
            self.execute_cursor2(delete_query)
            self.logger.log(f"Deleted record with key {existing_record_key} as part of replacing it.")
            return True  # next, insert the new record

        # Insert new record
        if response.lower() == self.INSERT:
            return True  # just insert the new record

    def insert_dict_into_main_db(self, download_dict, keys_set):
        """Insert records from downloadDict into the main table

        :param dict download_dict: The dictionary of records to (possibly) insert
        :param set keys_set: The existing transaction IDs in the database
        """
        # for key, val in download_dict.iteritems():
        for key in download_dict:
            val = download_dict[key]

            if '|' in key:
                old_key = key.split('|')[0]
                new_key = key.split('|')[1]
            else:
                old_key = key
                new_key = key

            # Check for same transaction IDs in database and don't insert them.
            if old_key in keys_set or old_key + '-0' in keys_set or new_key in keys_set or new_key \
                    + '-0' in keys_set:
                continue

            #
            # Check for possible duplicate records with different transaction IDs.
            #
            # For downloaded transactions whose key does not exist in the database, do one last
            # check for possible duplicates: same transaction date, amount, and description.
            # The credit union transactions downloads sometimes come back with different transaction IDs
            # for the same transactions downloaded at different times. Without this check, they
            # will get inserted into the database as duplicate transactions with different transaction 
            # IDs and cause problems that are hard to clean up later.
            # Check with the user if the record should be inserted anyway. If not, don't insert it.
            check_query = (f'SELECT tran_ID,tran_date,tran_desc,tran_checknum,tran_amount from main where '
                           f'tran_date=STR_TO_DATE("{val[0]}","%m/%d/%Y") and '
                           f'tran_desc="{val[2]}" and tran_amount="{val[5]}" and '
                           f'tran_checknum="{val[3]}";')
            self.execute_cursor1(check_query)

            # If the new record possibly matches an existing record, decide what to do with it
            if self.db_cursor1.rowcount > 0:
                self.logger.log("Possible duplicate record with different transaction ID")
                if not self._resolve_possible_duplicate_record(new_key, val):
                    continue  # skip inserting the new record

            # Insert the record into the database
            if self.DO_INSERT:
                my_query = ('INSERT into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,'
                            'tran_amount,bud_category,bud_amount,bud_date,comment) VALUES '
                            f'(STR_TO_DATE("{val[0]}","%m/%d/%Y"), "{new_key}", "{val[2][:120]}", '
                            f'"{(val[3] if val[3] else "0")}", "{val[4]}", "{val[5]}", "{val[6]}", "{str(val[7])}", '
                            f'STR_TO_DATE("{(val[8] if len(val[8]) else val[0])}","%m/%d/%Y"), "{val[9]}");')
                self.execute_cursor1(my_query)

                self.records_inserted += 1  # only increment the records_inserted counter here
            else:  # Log like we are doing an insert, but don't insert and don't count it
                val[1] = new_key

            self.logger.log(f"Key {new_key} is not in 'main' DATABASE -- "
                            f"{('' if self.DO_INSERT else 'would have ')}inserted {val}")

#
# MAIN PROGRAM
#


process_downloads = ProcessDownloads(do_insert=False)
process_downloads.execute()
