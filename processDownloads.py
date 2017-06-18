#!/usr/bin/python2

import MySQLdb
#import pymysql.cursors
import sys, os
import traceback
from transferFilesToDB import TransferMonthlyFilesToDB
from transferChecks import TransferChecks

def globalExceptionPrinter(exctype, value, tb):
    trs = ''
    for tr in traceback.format_list(traceback.extract_tb(tb)):
        trs += tr
    print('**********************************\nException occured\nType: '+
          str(exctype)+'\nValue: '+str(value)+'\nTraceback:\n'+trs+
          '*********************************')

def clearCUChecks():
    global cur1, cur2

    updated = 0
    try:
        query = ('select tran_checknum,tran_date from main where tran_checknum '
                 '!= "0" and tran_type = "b";')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('clearCUChecks(): Exception executing query: '+query)
        globalExceptionPrinter(etype, value, tb)
        sys.exit(1)

    for inner_row in cur1:
        checknum = str(inner_row[0])
        trandate = inner_row[1]

        query = ('update checks set clear_date = "'+str(trandate)+
                '" where tchecknum = "'+checknum+'";')
        try:
            cur2.execute(query)
        except:
            (etype, value, tb) = sys.exc_info()
            print('clearCUChecks(): Exception executing query: '+query)
            globalExceptionPrinter(etype, value, tb)
            sys.exit(1)

        updated += 1
    db.commit()
    print('Updated', updated, 'checks in checks database')




def printUnknownNonCheckTransactions():
    global cur1

    print('\nNon-check transactions marked "UNKNOWN" since 1/1/2006:')
    print('%-12s %-40s %10s' % ("Tran date", "Description", "Amount"))

    try:
        query = ('select tran_date,tran_desc,tran_amount from main where bud_ca'
                 'tegory = "UNKNOWN" and tran_date > "2005-12-31" and tran_desc'
                 ' not like "CHECK%" and tran_desc not like "Check%" order by t'
                 'ran_date;')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnknownNonCheckTransactions(): Exception executing query: '
              +query)
        globalExceptionPrinter(etype, value, tb)
        sys.exit(1)

    amount = 0
    for inner_row in cur1:
        print('%-12s %-40s $%10.2f' % (inner_row[0].strftime('%m/%d/%Y'),
              inner_row[1][:40], inner_row[2]))
        amount += inner_row[2]
    print('-----------------------------------------------------------------')
    print('%-53s $%10.2f' % ('Total:', amount))

def printUnRecordedChecks():
    global cur1, cur2

    print('\nCleared, unrecorded checks: ')
    print('%-5s %-12s %8s' % ("CNum", "Cleared date", "Amount"))

    try:
        query = ('select tran_checknum,tran_date,tran_amount from main where tr'
                 'an_checknum != "0" and tran_type = "b";')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnRecordedChecks(): Exception executing query: '+query)
        globalExceptionPrinter(etype, value, tb)
        sys.exit(1)

    # for every cleared CU check, see if it also exists as a transaction in
    # the checks database, with at least an amount
    for inner_row in cur1:
        try:
            query = ('select tchecknum from checks where tchecknum = "'+
                     str(inner_row[0])+'" and tamt is not null;')
            cur2.execute(query)
        except:
            (etype, value, tb) = sys.exc_info()
            print('printUnRecordedChecks(): Exception executing query: '+query)
            globalExceptionPrinter(etype, value, tb)
            sys.exit(1)

        if cur2.rowcount == 0:
            print('%-5d %-12s $%7.2f' % (inner_row[0],
                  inner_row[1].strftime('%m/%d/%Y'), abs(inner_row[2])))


def printUnclearedChecks():
    global cur1

    mydict = dict()
    print('\nUncleared checks since 1/1/2006: ')
    print('%-5s %-10s %8s %-30s %s' % ("CNum", "Date", "Amt", "Payee",
          "Comments"))
    try:
        query = ('select tnum,tdate,tamt,tpayee,comments from checks where clea'
                 'r_date is null and tdate > "2005-12-31" order by tnum;')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnclearedChecks(): Exception executing query: '+query)
        globalExceptionPrinter(etype, value, tb)
        sys.exit(1)

    for inner_row in cur1:
        key = (str(inner_row[1]) + inner_row[0] + str(abs(inner_row[2]))+
               inner_row[3] + inner_row[4])
        mydict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                       (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                        abs(inner_row[2]), inner_row[3], inner_row[4]))

    try:
        query = ('select tnum,tdate,tamt,tpayee,comments from chasechecks where'
                 ' clear_date is null and tdate > "2005-12-31" order by tnum;')
        cur1.execute(query)
    except:
        (etype, value, tb) = sys.exc_info()
        print('printUnclearedChecks(): Exception executing query: '+query)
        globalExceptionPrinter(etype, value, tb)
        sys.exit(1)

    for inner_row in cur1:
        key = (str(inner_row[1]) + inner_row[0] + str(abs(inner_row[2])) +
               inner_row[3] + inner_row[4])
        mydict[key] = ('%-5s %10s $%7.2f %-30s %s' %
                      (inner_row[0], inner_row[1].strftime('%m/%d/%Y'),
                       abs(inner_row[2]), inner_row[3], inner_row[4]))
    for entry in sorted(mydict):
        print(mydict[entry])

'''
def mergeDictIntoChecksDB(val):
    global cur1, doinsert

    # don't insert existing records into database, but check if existing record should be UPDATED
    # with tamt/tdate/tpayee/bud_cat/bud_amt/bud_date of new record
    cur1.execute('select tamt,tdate,tpayee from checks where tchecknum = "'+key+'";') # There may be multiple entries for this check if it's a multi-budget item
    cur1.fetchone() # only look at one record (of possible multiples)
    for row in cur1:
        if row[0] is None or row[1] is None or row[2] is None or not row[2]: # existing record is missing required fields
            if val[1] and val[2] and val[3]: # downloaded record with same key has all required fields
                if doinsert: # update the existing record with the required fields
                    cur1.execute('update checks set tamt="'+val[1]+'",tdate=STR_TO_DATE("'+val[2]+'","%m/%d/%Y"),tpayee="'+val[3]+'" where tchecknum = "'+key+'";')
                print('%spdated existing check # %s' % ('U' if doinsert else 'Would have u', key))
            else: # downloaded record does not have all required fields which existing record needs -- fail immediately
                print('Existing check '+key+' in checks database has empty required fields, but the downloaded record of the same key is missing required fields')
                print(val)
                sys.exit(1)
        else:
            print('Existing check # '+key+' does not need updating -- skipping')
'''

def insertDictIntoChecksDB(downloadDict, keysdict):
    '''
    The records in the downloadDict have all been processed so that bud_cat,
    bud_amt, and bud_date are filled in.
    '''
    global cur1, inserted, doinsert

    for key, val in downloadDict.iteritems():
        # existing record found -- ignore
        if key in keysdict or key+'-0' in keysdict: continue

        # downloaded record is new and does not exist in the checks database
        # key, checknum, amt, date, payee, bud[0], bud[1], bud[2], comment
        #         0       1    2      3     4cat     5amt   6date     7
        query = ('insert into checks (tnum,tchecknum,tamt,tdate,tpayee,bud_cat,'
                 'bud_amt,bud_date,comments) values ("'+val[0]+'","'+val[0]+'",'
                 '"'+val[1]+'","STR_TO_DATE("'+val[2]+'","%m/%d/%Y"),"'+val[3]+
                 '","'+val[4]+'","'+val[5]+'",STR_TO_DATE("'+val[6]+'","%m/%d/%'
                 'Y"),"'+val[7]+'");')

        # If inserting is enabled, insert into database
        if doinsert:
            try:
                cur1.execute(query)
                #cur1.commit()
            except:
                (etype, value, tb) = sys.exc_info()
                print('insertDictIntoChecksDB(): Exception executing query: '+
                      query)
                globalExceptionPrinter(etype, value, tb)
                sys.exit(1)

        print('Key '+key+' is not in "checks" database -- '+
              ('' if doinsert else 'would have ')+'inserted')
        inserted += 1




def insertDictIntoMainDB(downloadDict, keysdict):
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
        if oldkey in keysdict or oldkey+'-0' in keysdict or newkey in keysdict \
           or newkey+'-0' in keysdict:
            continue

        query = ('INSERT into main (tran_date,tran_ID,tran_desc,tran_checknum,t'
                 'ran_type,tran_amount,bud_category,bud_amount,bud_date,comment'
                 ') VALUES (STR_TO_DATE("'+val[0]+'","%m/%d/%Y"), "'+newkey+'",'
                 ' "'+val[2]+'", "'+(val[3] if val[3] else "0") +'", "'+val[4]+
                 '", "'+val[5]+'", "'+val[6]+'", "'+str(val[7])+'", STR_TO_DATE'
                 '("'+val[8]+'","%m/%d/%Y"), "'+val[9]+'");')

        # If inserting is enabled, insert into the appropriate database
        if doinsert:
            try:
                cur1.execute(query)
                #cur1.commit()
            except:
                (etype, value, tb) = sys.exc_info()
                print('insertDictIntoMainDB(): Exception executing query: '+
                      query)
                globalExceptionPrinter(etype, value, tb)
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
        print('The folder "downloads" is a symbolic link, but its target does n'
              'ot exist.')
        print('To restore it as a symbolic link, re-install vmware-tools:')
        print('1. cd /home/chrisanderson/Desktop/vmware-tools-distrib')
        print('2. "sudo perl vmware-install.pl" and enter password for chrisand'
              'erson')
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
db = MySQLdb.connect(host='localhost', user='root', passwd='sawtooth',
                     db='officialBudget')
#db = pymysql.connect(host='localhost', user='root', password='sawtooth',
#                     db='officialBudget')
cur1 = db.cursor()
cur2 = db.cursor()

# store the list of main DB keys for quick searching
try:
    query = 'SELECT tran_ID from main;'
    cur1.execute(query)
except:
    (etype, value, tb) = sys.exc_info()
    print('Main(): Exception executing query: '+query)
    globalExceptionPrinter(etype, value, tb)
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
    globalExceptionPrinter(etype, value, tb)
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

clearCUChecks() # mark cleared checks

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

print('\n'+('Inserted ' if doinsert else 'Did not insert ')+str(inserted)+
      ' records into DB')

printUnclearedChecks()
printUnRecordedChecks()
printUnknownNonCheckTransactions()
