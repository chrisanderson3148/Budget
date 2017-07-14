#!/usr/bin/python2

from __future__ import print_function
import MySQLdb
import sys
import os
import traceback
from transferFilesToDB import TransferMonthlyFilesToDB
from transferChecks import TransferChecks


def global_exception_printer(exception_type, val, trace_back):
    """Prints exceptions that are caught globally, ie, uncaught elsewhere

    :param types.ExceptionType exception_type: the caught exception type
    :param int val: the exception value
    :param Any trace_back: the exception traceback object
    """
    trs = ''
    for trcbck in traceback.format_list(traceback.extract_tb(trace_back)):
        trs += trcbck
    print('**********************************\nException occurred\nType: ' +
          str(exception_type) + '\nValue: ' + str(val) + '\nTraceback:\n' + trs +
          '*********************************')


def clear_cu_checks():
    """Runs query to identify main table check entries and attempt to clear them"""
    global cur1, cur2

    updated = 0
    query = ('select tran_checknum,tran_date from main where tran_checknum != "0" and tran_type = "b";')
    try:
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('clearCUChecks(): Exception executing query: '+query)
        global_exception_printer(etype, value, tb)
        sys.exit(1)

    for inner_row in cur1:
        checknum = str(inner_row[0])
        trandate = inner_row[1]

        query = ('update checks set clear_date = "'+str(trandate)+'" where tchecknum = "'+checknum+'";')
        try:
            cur2.execute(query)
        except:
            (etype, value, tb) = sys.exc_info()
            print('clearCUChecks(): Exception executing query: '+query)
            global_exception_printer(etype, value, tb)
            sys.exit(1)

        updated += 1
    db.commit()
    print('Updated', updated, 'checks in checks database')


def printUnknownNonCheckTransactions():
    """Print a list of unknown, non-check transactions"""
    global cur1

    print('\nNon-check transactions marked "UNKNOWN" since 1/1/2006:')
    print('%-12s %-40s %10s' % ("Tran date", "Description", "Amount"))

    try:
        query = ('select tran_date,tran_desc,tran_amount from main where bud_category = "UNKNOWN" and tr'
                 'an_date > "2005-12-31" and tran_desc not like "CHECK%" and tran_desc not like "Check%"'
                 ' order by tran_date;')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnknownNonCheckTransactions(): Exception executing query: '+query)
        global_exception_printer(etype, value, tb)
        sys.exit(1)

    amount = 0
    for inner_row in cur1:
        print('%-12s %-40s $%10.2f' % (inner_row[0].strftime('%m/%d/%Y'),
                                       inner_row[1][:40], inner_row[2]))
        amount += inner_row[2]
    print('-----------------------------------------------------------------')
    print('%-53s $%10.2f' % ('Total:', amount))

def printUnRecordedChecks():
    """Print a list of unrecorded checks"""
    global cur1, cur2

    print('\nCleared, unrecorded checks: ')
    print('%-5s %-12s %8s' % ("CNum", "Cleared date", "Amount"))

    try:
        query = ('select tran_checknum,tran_date,tran_amount from main where tran_checknum != "0" and tr'
                 'an_type = "b";')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnRecordedChecks(): Exception executing query: '+query)
        global_exception_printer(etype, value, tb)
        sys.exit(1)

    # for every cleared CU check, see if it also exists as a transaction in
    # the checks database, with at least an amount
    for inner_row in cur1:
        try:
            query = ('select tchecknum from checks where tchecknum = "'+str(inner_row[0])
                     +'" and tamt is not null;')
            cur2.execute(query)
        except:
            (etype, value, tb) = sys.exc_info()
            print('printUnRecordedChecks(): Exception executing query: '+query)
            global_exception_printer(etype, value, tb)
            sys.exit(1)

        if cur2.rowcount == 0:
            print('%-5d %-12s $%7.2f' % (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                                         abs(inner_row[2])))


def printUnclearedChecks():
    """Print a list of uncleared checks"""
    global cur1

    mydict = dict()
    print('\nUncleared checks since 1/1/2006: ')
    print('%-5s %-10s %8s %-30s %s' % ("CNum", "Date", "Amt", "Payee", "Comments"))
    try:
        # uncleared checks have no cleared date, transacted in 2006 or later, and have an amount (not
        # cancelled)
        query = ('select tnum,tdate,tamt,tpayee,comments from checks where clear_date is null and tdate '
                 '> "2005-12-31" and tamt != 0.0 order by tnum;')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnclearedChecks(): Exception executing query: '+query)
        global_exception_printer(etype, value, tb)
        sys.exit(1)

    for inner_row in cur1:
        key = (str(inner_row[1])+inner_row[0]+str(abs(inner_row[2]))+inner_row[3]+inner_row[4])
        mydict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                       (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                        abs(inner_row[2]), inner_row[3], inner_row[4]))

    try:
        query = ('select tnum,tdate,tamt,tpayee,comments from chasechecks where clear_date is null and t'
                 'date > "2005-12-31" and tamt != 0.0  order by tnum;')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnclearedChecks(): Exception executing query: '+query)
        global_exception_printer(etype, value, tb)
        sys.exit(1)

    for inner_row in cur1:
        key = (str(inner_row[1]) + inner_row[0] + str(abs(inner_row[2])) + inner_row[3] + inner_row[4])
        mydict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                       (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                        abs(inner_row[2]), inner_row[3], inner_row[4]))
    for entry in sorted(mydict):
        print(mydict[entry])

def insertDictIntoChecksDB(downloadDict, keysdict):
    """Insert checks in downloadDict into the checks database

    The records in the downloadDict have all been processed so that bud_cat, bud_amt, and bud_date are
    filled in.

    :param dict downloadDict: the records to insert
    :param dict keysdict: Later
    """
    global cur1, inserted, doinsert

    for key, val in downloadDict.iteritems():
        # existing record found -- ignore
        if key in keysdict or key+'-0' in keysdict: continue

        # downloaded record is new and does not exist in the checks database
        # key, checknum, amt, date, payee, bud[0], bud[1], bud[2], comment
        #         0       1    2      3     4cat     5amt   6date     7
        query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_date,comments'
                 ') values ("'+val[0]+'","'+val[0]+'","'+val[1]+'","STR_TO_DATE("'+val[2]+'","%m/%d/%Y")'
                 ',"'+val[3]+'","'+val[4]+'","'+val[5]+'",STR_TO_DATE("'+val[6]+'","%m/%d/%Y"),"'+val[7]
                 +'");')
        # If inserting is enabled, insert into database
        if doinsert:
            try:
                cur1.execute(query)
                #cur1.commit()
            except:
                (etype, value, tb) = sys.exc_info()
                print('insertDictIntoChecksDB(): Exception executing query: '+query)
                global_exception_printer(etype, value, tb)
                sys.exit(1)

        print('Key '+key+' is not in "checks" database -- '+('' if doinsert else 'would have ')
              +'inserted')
        inserted += 1

def insertDictIntoMainDB(downloadDict, keysdict):
    """Insert records from downloadDict into the main table

    :param dict downloadDict:
    :param dict keysdict:
    """
    global cur1, inserted, doinsert

    for key, val in downloadDict.iteritems():
        if '|' in key:
            oldkey = key.split('|')[0]
            newkey = key.split('|')[1]
            #print('newkey='+newkey+', oldkey='+oldkey)
        else:
            oldkey = key
            newkey = key

        # don't insert existing records into database, but check if should
        # UPDATE the existing record
        if oldkey in keysdict or oldkey+'-0' in keysdict or newkey in keysdict or newkey+'-0' \
                in keysdict:
            continue

        query = ('INSERT into main (tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran_amount,bud_'
                 'category,bud_amount,bud_date,comment) VALUES (STR_TO_DATE("'+val[0]+'","%m/%d/%Y"), "'
                 +newkey+'", "'+val[2]+'", "'+(val[3] if val[3] else "0") +'", "'+val[4]+'", "'+val[5]
                 +'", "'+val[6]+'", "'+str(val[7])+'", STR_TO_DATE("'+val[8]+'","%m/%d/%Y"), "'+val[9]
                 +'");')

        # If inserting is enabled, insert into the appropriate database
        if doinsert:
            try:
                cur1.execute(query)
                #cur1.commit()
            except:
                (etype, value, tb) = sys.exc_info()
                print('insertDictIntoMainDB(): Exception executing query: '+query)
                global_exception_printer(etype, value, tb)
                sys.exit(1)
        else:
            val[1] = newkey
            print('Key '+newkey+' is not in "main" database -- '+
                  ('' if doinsert else 'would have ')+'inserted', val)
        inserted += 1


#
# MAIN SCRIPT HERE
#

# Set some static strings
cufile = 'downloads/ExportedTransactions.csv'
# cufile = 'downloads/HistoryDownload.csv'
ckfile = 'downloads/checks'
axfile = 'downloads/ofx.csv'
difile = 'downloads/Discover-RecentActivity.csv'
byfile = 'downloads/BarclayCard.qfx'
cifile = 'downloads/Citi-RecentActivity.csv'

# Verify symbolic link to 'downloads' is not broken
if os.path.isdir('downloads'):
    if os.path.islink('downloads') and \
            not os.path.exists(os.readlink('downloads')):
        print('The folder "downloads" is a symbolic link, but its target does not exist.')
        print('To restore it as a symbolic link, re-install vmware-tools:')
        print('1. cd /home/chrisanderson/Desktop/vmware-tools-distrib')
        print('2. "sudo perl vmware-install.pl" and enter password for chrisanderson')
        print('3. Answer all questions with the default (just hit <return>)')
        sys.exit(1)

# Verify all downloads files exist
allexist = True
for dfile in [cufile, ckfile, axfile, difile, byfile, cifile]:
    if not os.path.exists(dfile):
        print('Download file "' + dfile + '" does not exist')
        allexist = False
if not allexist: sys.exit(1)

# Set up some globals
doinsert = True # set to True to actually insert into database
inserted = 0

# Open a connection to the database
db = MySQLdb.connect(host='localhost', user='root', passwd='sawtooth', db='officialBudget')
#db = pymysql.connect(host='localhost', user='root', password='sawtooth', db='officialBudget')
cur1 = db.cursor()
cur2 = db.cursor()

# store the list of main DB keys for quick searching
try:
    query = 'SELECT tran_ID from main;'
    cur1.execute(query)
except:
    (etype, value, tb) = sys.exc_info()
    print('Main(): Exception executing query: '+query)
    global_exception_printer(etype, value, tb)
    sys.exit(1)

dbkeys = set()
for row in cur1:
    dbkeys.add(row[0])

try:
    query = 'SELECT tnum from checks;'
    cur1.execute(query)
except:
    (etype, value, tb) = sys.exc_info()
    print('Main(): Exception executing query: '+query)
    global_exception_printer(etype, value, tb)
    sys.exit(1)

ckkeys = set()
for row in cur1:
    ckkeys.add(row[0])

tf = TransferMonthlyFilesToDB(cur1)
ck = TransferChecks()

# handle credit union transactions including checks
if os.path.isfile(ckfile): # process checks first
    print('\nprocessing credit union checks download file...')
    CK_dict = ck.readChecksFile(ckfile)
    insertDictIntoChecksDB(CK_dict, ckkeys)

if os.path.isfile(cufile): # process cleared transactions second
    print('\nprocessing credit union download file...')
    CU_dict = tf.readMonthlyCUFile(cufile)
    insertDictIntoMainDB(CU_dict, dbkeys)

clear_cu_checks() # mark cleared checks

if os.path.isfile(axfile):
    print('\nprocessing American Express download file...')
    AE_dict = tf.readMonthlyAmexFile(axfile)
    insertDictIntoMainDB(AE_dict, dbkeys)

if os.path.isfile(cifile):
    print('\nprocessing CitiCard download file...')
    CI_dict = tf.readMonthlyCitiFile(cifile)
    insertDictIntoMainDB(CI_dict, dbkeys)

if os.path.isfile(difile):
    print('\nprocessing Discover download file...')

    # process a download file, not a monthly file
    DC_dict = tf.readMonthlyDiscoverFile(difile, True)
    insertDictIntoMainDB(DC_dict, dbkeys)

# CH_dict = tf.readMonthlyChaseFile(fname)
# insertDictIntoMainDB(CH_dict)

if os.path.isfile(byfile):
    print('\nprocessing Barclay download file...')
    BC_dict = tf.readDownloadBarclayFile(byfile)
    insertDictIntoMainDB(BC_dict, dbkeys)

print('\n'+('Inserted ' if doinsert else 'Did not insert ')+str(inserted)+' records into DB')

printUnclearedChecks()
printUnRecordedChecks()
printUnknownNonCheckTransactions()
