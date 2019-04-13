#!/usr/bin/python2

from __future__ import print_function
import sys
import os
import traceback
import MySQLdb
import transferCheckUtils
import utils
from transferFilesToDB import TransferMonthlyFilesToDB
from transferChecks import TransferChecks


def global_exception_printer(e_type, val, trace_back):
    """Prints exceptions that are caught globally, ie, uncaught elsewhere

    :param types.ExceptionType e_type: the caught exception type
    :param int val: the exception value
    :param Any trace_back: the exception traceback object
    """
    trs = ''
    for my_trace_back in traceback.format_list(traceback.extract_tb(trace_back)):
        trs += my_trace_back
    utils.logger('**********************************\nException occurred\nType: ' +
                 str(e_type) + '\nValue: ' + str(val) + '\nTraceback:\n' + trs +
                 '*********************************')


def clear_cu_checks():
    """Runs query to identify main table check entries and attempt to clear them"""
    global CURSOR1, CURSOR2

    updated = 0
    local_query = ('select tran_checknum,tran_date from main where tran_checknum != "0" and '
                   'tran_type = "b";')
    try:
        CURSOR1.execute(local_query)
    except MySQLdb.Error:
        (my_exception_type, my_value, my_tb) = sys.exc_info()
        utils.logger('clearCUChecks(): Exception executing query: '+local_query)
        global_exception_printer(my_exception_type, my_value, my_tb)
        sys.exit(1)

    for inner_row in CURSOR1:
        check_num = str(inner_row[0])
        transaction_date = inner_row[1]

        local_query = ('update checks set clear_date = "'+str(transaction_date)+'" where tchecknum = "'
                       + check_num+'";')
        try:
            CURSOR2.execute(local_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            utils.logger('clearCUChecks(): Exception executing query: '+local_query)
            global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        updated += 1
    DB.commit()
    utils.logger('Updated {} checks in checks DATABASE'.format(updated))


def print_unknown_non_check_transactions():
    """Print a list of unknown, non-check transactions"""
    global CURSOR1

    utils.logger('\nNon-check transactions marked "UNKNOWN" since 1/1/2006:')
    utils.logger('%-12s %-40s %10s' % ("Tran date", "Description", "Amount"))

    my_query = ('select tran_date,tran_desc,tran_amount from main where bud_category = "UNKNOWN" and '
                'tran_date > "2005-12-31" and tran_desc not like "CHECK%" and tran_desc not like '
                '"Check%" order by tran_date;')
    try:
        CURSOR1.execute(my_query)
    except MySQLdb.Error:
        (my_exception_type, my_value, my_tb) = sys.exc_info()
        utils.logger('print_unknown_non_check_transactions(): Exception executing query: '+my_query)
        global_exception_printer(my_exception_type, my_value, my_tb)
        sys.exit(1)

    amount = 0
    for inner_row in CURSOR1:
        utils.logger('%-12s %-40s $%10.2f' % (inner_row[0].strftime('%m/%d/%Y'),
                                              inner_row[1][:40], inner_row[2]))
        amount += inner_row[2]
    utils.logger('-----------------------------------------------------------------')
    utils.logger('%-53s $%10.2f' % ('Total:', amount))


def print_unrecorded_checks():
    """Print a list of unrecorded checks"""
    global CURSOR1, CURSOR2

    utils.logger('\nCleared, unrecorded checks: ')
    utils.logger('%-5s %-12s %8s' % ("CNum", "Cleared date", "Amount"))

    my_query = ('select tran_checknum,tran_date,tran_amount from main where tran_checknum != "0" and'
                ' tran_type = "b";')
    try:
        CURSOR1.execute(my_query)
    except MySQLdb.Error:
        (my_exception_type, my_value, my_tb) = sys.exc_info()
        utils.logger('print_unrecorded_checks(): Exception executing query: '+my_query)
        global_exception_printer(my_exception_type, my_value, my_tb)
        sys.exit(1)

    # for every cleared CU check, see if it also exists as a transaction in
    # the checks DATABASE, with at least an amount
    for inner_row in CURSOR1:
        my_query = ('select tchecknum from checks where tchecknum = "'+str(inner_row[0])
                    + '" and tamt is not null;')
        try:
            CURSOR2.execute(my_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            utils.logger('print_unrecorded_checks(): Exception executing query: '+my_query)
            global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        if CURSOR2.rowcount == 0:
            utils.logger('%-5d %-12s $%7.2f' % (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                                                abs(inner_row[2])))


def print_uncleared_checks():
    """Print a list of uncleared checks"""
    global CURSOR1

    my_dict = dict()
    utils.logger('\nUncleared checks since 1/1/2006: ')
    utils.logger('%-5s %-10s %8s %-30s %s' % ("CNum", "Date", "Amt", "Payee", "Comments"))

    my_query = ('select tnum,tdate,tamt,tpayee,comments from checks where clear_date is null and tdate '
                '> "2005-12-31" and tamt != 0.0 order by tnum;')
    try:
        # uncleared checks have no cleared date, transacted in 2006 or later, and have an amount (not
        # cancelled)
        CURSOR1.execute(my_query)
    except MySQLdb.Error:
        (my_exception_type, my_value, my_tb) = sys.exc_info()
        utils.logger('print_uncleared_checks(): Exception executing query: '+my_query)
        global_exception_printer(my_exception_type, my_value, my_tb)
        sys.exit(1)

    for inner_row in CURSOR1:
        key = (str(inner_row[1])+inner_row[0]+str(abs(inner_row[2]))+inner_row[3]+inner_row[4])
        my_dict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                        (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                         abs(inner_row[2]), inner_row[3], inner_row[4]))

    my_query = ('select tnum,tdate,tamt,tpayee,comments from chasechecks where clear_date is null and t'
                'date > "2005-12-31" and tamt != 0.0  order by tnum;')
    try:
        CURSOR1.execute(my_query)
    except MySQLdb.Error:
        (my_exception_type, my_value, my_tb) = sys.exc_info()
        utils.logger('print_uncleared_checks(): Exception executing query: '+my_query)
        global_exception_printer(my_exception_type, my_value, my_tb)
        sys.exit(1)

    for inner_row in CURSOR1:
        key = (str(inner_row[1]) + inner_row[0] + str(abs(inner_row[2])) + inner_row[3] + inner_row[4])
        my_dict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                        (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                         abs(inner_row[2]), inner_row[3], inner_row[4]))
    for entry in sorted(my_dict):
        utils.logger(my_dict[entry])


def insert_dict_into_checks_db(download_dict, keys_set):
    """Insert checks in downloadDict into the checks DATABASE

    The records in the downloadDict have all been processed so that bud_cat, bud_amt, and bud_date are
    filled in.

    :param dict download_dict: the records to insert
    :param set keys_set: Later
    """
    global CURSOR1, records_inserted, DO_INSERT

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
        if DO_INSERT:
            try:
                CURSOR1.execute(my_query)
            except MySQLdb.Error:
                (my_exception_type, my_value, my_tb) = sys.exc_info()
                utils.logger('insert_dict_into_checks_db(): Exception executing query: '+my_query)
                global_exception_printer(my_exception_type, my_value, my_tb)
                sys.exit(1)

        utils.logger('Key '+key+' is not in "checks" DATABASE -- '+('' if DO_INSERT else 'would have ')
                     + 'inserted')
        records_inserted += 1


def insert_dict_into_main_db(download_dict, keys_set):
    """Insert records from downloadDict into the main table

    :param dict download_dict:
    :param set keys_set:
    """
    global CURSOR1, CURSOR2, records_inserted, DO_INSERT

    for key, val in download_dict.iteritems():
        if '|' in key:
            old_key = key.split('|')[0]
            new_key = key.split('|')[1]
        else:
            old_key = key
            new_key = key

        # don't insert existing records into DATABASE, but check if should
        # UPDATE the existing record
        if old_key in keys_set or old_key + '-0' in keys_set or new_key in keys_set or new_key\
                + '-0' in keys_set:
            continue

        # For downloaded transactions whose key does not exist in the database, do one last
        # check for possible duplicates: same transaction date, amount, and description.
        # The credit union transactions downloads sometimes come back with different transaction IDs
        # for the same transactions downloaded at different times. Without this check, they
        # will get inserted into the database as duplicate transactions and cause problems that are
        # hard to clean up later.
        # Check with the user if the record should be inserted anyway. If not, don't insert it.
        check_query = ('SELECT tran_ID,tran_date,tran_desc,tran_checknum,tran_amount from main where '
                       'tran_date=STR_TO_DATE("'+val[0]+'","%m/%d/%Y") and '
                       'tran_desc="'+val[2]+'" and tran_amount="'+val[5]+'" and '
                       'tran_checknum="'+val[3]+'";')
        try:
            CURSOR1.execute(check_query)
        except MySQLdb.Error:
            (my_exception_type, my_value, my_tb) = sys.exc_info()
            utils.logger('insert_dict_into_main_db(): Exception executing query: {}'.format(check_query))
            global_exception_printer(my_exception_type, my_value, my_tb)
            sys.exit(1)

        #
        # One match - insert or ignore new record, or replace existing record with it.
        #
        if CURSOR1.rowcount == 1:
            utils.logger('Possible duplicate record with different transaction ID (existing record VS '
                         'candidate record):')
            existing_record_key = ''
            for row in CURSOR1:
                existing_record_key = row[0]
                utils.logger('old "{}" "{}" "{}" "{}" "{}" VS new "{}" "{}" "{}" "{}" "{}"'
                             .format(row[0], row[1], row[2], row[3], row[4], new_key, val[0], val[2],
                                     (val[3] if val[3] else "0"), val[5]))
            response = raw_input("What to do with this record: [insert|ignore|replace (existing)]? ")
            utils.logger('response="{}"'.format(response))
            if response.lower().startswith('ignore'):
                continue  # do NOT insert this record!!
            if response.lower().startswith('replace'):  # delete existing record first
                delete_query = 'DELETE FROM main where tran_id = "{}";'.format(existing_record_key)
                try:
                    # delete existing record from database (first part of replacing with new record)
                    CURSOR2.execute(delete_query)
                except MySQLdb.Error:
                    (my_exception_type, my_value, my_tb) = sys.exc_info()
                    utils.logger('insert_dict_into_main_db(): Exception executing query: '+delete_query)
                    global_exception_printer(my_exception_type, my_value, my_tb)
                    sys.exit(1)
            # otherwise, keep going and insert it

        #
        # More than one match - insert or ignore new record, no replace
        #
        elif CURSOR1.rowcount > 1:
            utils.logger('Possible duplicate records with different transaction IDs (existing record VS '
                         'candidate records):')
            for row in CURSOR1:
                utils.logger('Existing record: "{}" "{}" "{}" "{}" "{}"\nNew record:      "{}" "{}" '
                             '"{}" "{}" "{}"'.format(
                                    row[0], row[1], row[2], row[3], row[4], new_key, val[0], val[2],
                                    (val[3] if val[3] else "0"), val[5]))
            response = raw_input("Insert or ignore new record [insert|ignore]? ")
            if response.lower().startswith('ignore'):
                continue  # do NOT insert the record
            # otherwise keep going and insert it

        # It seems to check out -- insert into the database
        my_query = ('INSERT into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran_amount,'
                    'bud_category,bud_amount,bud_date,comment) VALUES '
                    '(STR_TO_DATE("'+val[0]+'","%m/%d/%Y"), "' + new_key+'", "'+val[2]+'", "'
                    + (val[3] if val[3] else "0")+'", "'+val[4]+'", "'+val[5]+'", "'+val[6]+'", "'
                    + str(val[7])+'", STR_TO_DATE("'+(val[8] if len(val[8]) else val[0])
                    + '","%m/%d/%Y"), "'+val[9]+'");')

        # If inserting is enabled, insert into the appropriate DATABASE
        if DO_INSERT:
            try:
                CURSOR1.execute(my_query)
            except MySQLdb.Error:
                (my_exception_type, my_value, my_tb) = sys.exc_info()
                utils.logger('insert_dict_into_main_db(): Exception executing query: '+my_query)
                global_exception_printer(my_exception_type, my_value, my_tb)
                sys.exit(1)
        else:
            val[1] = new_key
            utils.logger('Key {} is not in "main" DATABASE -- {}inserted {}'.format(
                new_key, ('' if DO_INSERT else 'would have '), val))
        records_inserted += 1


#
# MAIN SCRIPT HERE
#

# Set some static strings
CU_FILE = 'downloads/ExportedTransactions.csv'
# CU_FILE = 'downloads/HistoryDownload.csv'
CK_FILE = 'downloads/checks'
# AX_FILE = 'downloads/ofx.csv'
DI_FILE = 'downloads/Discover-RecentActivity.csv'
# BY_FILE = 'downloads/BarclayCard.qfx'
CI_FILE = 'downloads/Citi-RecentActivity.csv'

# Verify symbolic link to 'downloads' is not broken
if os.path.isdir('downloads'):
    if os.path.islink('downloads') and not os.path.exists(os.readlink('downloads')):
        utils.logger('The folder "downloads" is a symbolic link, but its target does not exist.')
        utils.logger('To restore it as a symbolic link, re-install vmware-tools:')
        utils.logger('1. cd /home/chrisanderson/Desktop/vmware-tools-distrib')
        utils.logger('2. "sudo perl vmware-install.pl" and enter password for chrisanderson')
        utils.logger('3. Answer all questions with the default (just hit <return>)')
        sys.exit(1)

# Verify all downloads files exist
all_exist = True
for download_file in [CU_FILE, CK_FILE, DI_FILE, CI_FILE]:
    if not os.path.exists(download_file):
        utils.logger('Download file "' + download_file + '" does not exist')
        all_exist = False
if not all_exist:
    sys.exit(1)

# Set up some globals
DO_INSERT = True  # set to True to actually insert into DATABASE
records_inserted = 0

# Open a connection to the DATABASE
DB = MySQLdb.connect(host='localhost', user='root', passwd='sawtooth', db='officialBudget')
CURSOR1 = DB.cursor()
CURSOR2 = DB.cursor()

# store the list of main DB keys for quick searching
query = 'SELECT tran_ID from main;'
try:
    CURSOR1.execute(query)
except MySQLdb.Error:
    (exception_type, value, tb) = sys.exc_info()
    utils.logger('Main(): Exception executing query: '+query)
    global_exception_printer(exception_type, value, tb)
    sys.exit(1)

db_keys = set()
for row in CURSOR1:
    db_keys.add(row[0])

query = 'SELECT tnum from checks;'
try:
    CURSOR1.execute(query)
except MySQLdb.Error:
    (exception_type, value, tb) = sys.exc_info()
    utils.logger('Main(): Exception executing query: '+query)
    global_exception_printer(exception_type, value, tb)
    sys.exit(1)

ck_keys = set()
for row in CURSOR1:
    ck_keys.add(row[0])

TF = TransferMonthlyFilesToDB(CURSOR1)

# handle credit union transactions including checks
if os.path.isfile(CK_FILE):  # process checks first
    utils.logger('\nprocessing credit union checks download file...')
    CK_dict = transferCheckUtils.read_checks_file(CK_FILE)
    insert_dict_into_checks_db(CK_dict, ck_keys)

if os.path.isfile(CU_FILE):  # process cleared transactions second
    utils.logger('\nprocessing credit union download file...')
    CU_dict = TF.read_monthly_cu_file(CU_FILE)
    insert_dict_into_main_db(CU_dict, db_keys)

clear_cu_checks()  # mark cleared checks

# if os.path.isfile(AX_FILE):
#     utils.logger('\nprocessing American Express download file...')
#     AE_dict = TF.read_monthly_amex_file(AX_FILE)
#     insert_dict_into_main_db(AE_dict, db_keys)

if os.path.isfile(CI_FILE):
    utils.logger('\nprocessing CitiCard download file...')
    CI_dict = TF.read_monthly_citi_file(CI_FILE)
    insert_dict_into_main_db(CI_dict, db_keys)

if os.path.isfile(DI_FILE):
    utils.logger('\nprocessing Discover download file...')

    # process a download file, not a monthly file
    DC_dict = TF.read_monthly_discover_file(DI_FILE, True)
    insert_dict_into_main_db(DC_dict, db_keys)

# if os.path.isfile(BY_FILE):
#     utils.logger('\nprocessing Barclay download file...')
#     BY_dict = TF.read_download_barclay_file(BY_FILE)
#     insert_dict_into_main_db(BY_dict, db_keys)

utils.logger('\n' + ('Inserted ' if DO_INSERT else 'Did not insert ') + str(records_inserted)
             + ' records into DB')

print_uncleared_checks()
print_unrecorded_checks()
print_unknown_non_check_transactions()
