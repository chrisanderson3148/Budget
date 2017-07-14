#!/usr/bin/python

import MySQLdb
import sys, os
from transferFilesToDB import TransferMonthlyFilesToDB

'''
We create the monthly budget summary file by combining the results of the 'main' table and the 'checks'
table and listing each budget total for the month as well as the transactions making up that total.
The CU check transactions in the 'main' table are ignored and only the tran_checknumber field is used to
link the two tables.  All the CU checks transactions for the given month are taken from the checks table.

Definitions:

    Uncleared checks: recorded in the 'checks' table but don't have a corresponding entry in the 'main'
    table -- they are 'in flight' and haven't cleared the bank yet.  Their clear_date field in the
    'checks' table is null. They show up with an '*' after the amount in the monthly budget summary file.

    Unrecorded checks: were written but not recorded in the 'checks' table. When they clear the bank,
    they show up in the 'main' table as cleared transactions, but are ignored (the tran_checknum field
    points to a non-existent entry in the 'checks' table.) Their amounts are not counted in the monthly
    budget total and they do not show up in that file at all. It is important to record checks into the
    'checks' table as soon as they are written.

The list of uncleared checks, and the list of unrecorded checks are printed at the end of running the
processDownloads.py script. That script also takes care of 'clearing' each check whose transaction is
found in the 'main' table by updating the clear_date field in the corresponding entry in the 'checks'
table with the tran_date from the 'main' table entry.
'''

# Open a connection to the database
db = MySQLdb.connect(host='localhost', user='root', passwd='sawtooth', db='officialBudget')
cur = db.cursor()

# month is 1-based
def writeMonthCsv(year, month):
    """Write the CSV file with 'year' and 'month' part of the file name
    
    :param str year: the year as a string
    :param str month: the month name
    """
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # get the budget categories and sums for the time period from 'main'
    buds_summary = dict()
    cur.execute("SELECT bud_category,sum(bud_amount) from main where bud_date between '"
                +year+"-"+month+"-01' and '"+year+"-"+month+"-31' and tran_checknum = '0' "
                "and tran_desc not like 'CHECK %' group by bud_category order by bud_category;")

    rows = cur.fetchall()
    # save results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL': key = 'COLLEGE'
        buds_summary[key] = row[1]

    # get the budget categories and sums for the time period from 'checks'
    cur.execute("SELECT bud_cat,sum(bud_amt) from checks where bud_date between '"+year+"-"+month+"-01' "
                "and '"+year+"-"+month+"-31' group by bud_cat;")
    rows = cur.fetchall()
    # update results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL': key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]

    # get the budget categories and sums for the time period from 'chasechecks'
    cur.execute("SELECT bud_cat,sum(bud_amt) from chasechecks where bud_date between '"
                +year+"-"+month+"-01' and '"+year+"-"+month+"-31' group by bud_cat;")
    rows = cur.fetchall()
    # update results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL': key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]

    name = month_names[int(month)-1]+' '+year

    # see if there are any results to save to the file
    if len(buds_summary) == 0:
        print 'writeMonthlyCsv: No entries for month '+name
        return
    else:
        print('writeMonthlyCsv: Month '+name+' has', len(buds_summary), 'entries')

    # write out to the file
    with open('catfiles/'+name.replace(' ', '')+'cat.csv', 'w') as f:
        f.write('Summary for '+name+'\r\n')
        for budcat in sorted(buds_summary):
            f.write('%s,%.2f\r\n' % (budcat, buds_summary[budcat]))

# month is 1-based
def writeMonthText(year, month):
    """Write the txt file with 'year' and 'month' part of the file name
    
    :param str year: the year as a string
    :param str month: the month name
    """
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # get the budget categories and sums for the time period from 'main'
    buds_summary = dict()
    cur.execute("SELECT bud_category,sum(bud_amount) from main where bud_date between '"
                +year+"-"+month+"-01' and '"+year+"-"+month+"-31' and tran_checknum = '0' and "
                "tran_desc not like 'CHECK %' group by bud_category order by bud_category;")
    rows = cur.fetchall()

    # save results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL': key = 'COLLEGE'
        buds_summary[key] = row[1]

    # get the budget categories and sums for the time period from 'checks'
    cur.execute("SELECT bud_cat,sum(bud_amt) from checks where bud_date between '"+year+"-"+month+"-01' "
                "and '"+year+"-"+month+"-31' group by bud_cat;")
    rows = cur.fetchall()

    # update the results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL': key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]


    # get the budget categories and sums for the time period from 'chasechecks'
    cur.execute("SELECT bud_cat,sum(bud_amt) from chasechecks where bud_date between '"
                +year+"-"+month+"-01' and '"+year+"-"+month+"-31' group by bud_cat;")
    rows = cur.fetchall()

    # update the results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL': key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]

    name = month_names[int(month)-1]+' '+year

    # see if there are any results to save to the file
    if len(buds_summary) == 0:
        print 'writeMonthlyText: No entries for month '+name
        return
    else:
        print('writeMonthlyText: Month '+name+' has', len(buds_summary), 'entries')

    # write out to the file
    with open('catfiles/'+name.replace(' ', '')+'cat.txt', 'w') as f:
        f.write('Summary for '+name+'\r\n\r\n')

        # Now go through each budget category and print the individual transactions for each
        for budcat in sorted(buds_summary):
            # print the summary line
            f.write('%-20s %10.2f\r\n' % (budcat, buds_summary[budcat]))

            # dictionary to store all the 'main' table results and uncleared check results for later
            # printing
            sdict = dict()

            # select the 'main' table non-check (both Chase and CU) transactions that make up that
            # month/budget summary and store in dict
            if budcat == 'COLLEGE':
                query = ("SELECT tran_ID,tran_date,tran_type,tran_desc,bud_amount FROM main WHERE "
                         "bud_date between '"+year+"-"+month+"-01' and '"+year+"-"+month+"-31' and "
                         "(bud_category = 'COLLEGE' or bud_category = 'SCHOOL') and "
                         "tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;")
            else:
                query = ("SELECT tran_ID,tran_date,tran_type,tran_desc,bud_amount FROM main WHERE "
                         "bud_date between '"+year+"-"+month+"-01' and '"+year+"-"+month+"-31' and "
                         "bud_category = '"+budcat+"' and tran_checknum = '0' and "
                         "tran_desc not like 'CHECK %' order by bud_date;")
            cur.execute(query)
            for elem in cur:
                sdict[elem[1].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[1].strftime('%m/%d')+' '+elem[2]
                                                            +' %-40s'%elem[3][:40]+' %10.2f'%elem[4])

            # select the 'checks' table transactions that make up that
            # month/budget summary and store in dict
            if budcat == 'COLLEGE':
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date,comments FROM checks "
                         "WHERE bud_date between '"+year+"-"+month+"-01' and '"+year+"-"+month+"-31' "
                         "and (bud_cat = 'COLLEGE' or bud_cat = 'SCHOOL') order by tdate;")
            else:
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date,comments FROM checks "
                         "WHERE bud_date between '"+year+"-"+month+"-01' and '"+year+"-"+month+"-31' "
                         "and bud_cat = '"+budcat+"' order by tdate;")
            cur.execute(query)
            checks = cur.fetchall()
            for elem in checks:
                desc = ('Check '+str(elem[1])+': '+elem[2]+('|'+elem[6] if elem[6] else ''))
                sdict[elem[4].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[4].strftime('%m/%d')
                                                             +' b %-40s'%desc[:40]+ ' %10.2f'%elem[3]
                                                             +'%s'%('*' if elem[5] is None else ''))

            # select the 'chasechecks' table transactions that make up that month/budget summary and
            # store in dict
            if budcat == 'COLLEGE':
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date FROM chasechecks WHERE "
                         "bud_date between '"+year+"-"+month+"-01' and '"+year+"-"+month+"-31' and "
                         "(bud_cat = 'COLLEGE' or bud_cat = 'SCHOOL') order by tdate;")
            else:
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date FROM chasechecks WHERE "
                         "bud_date between '"+year+"-"+month+"-01' and '"+year+"-"+month+"-31' and "
                         "bud_cat = '"+budcat+"' order by tdate;")
            cur.execute(query)
            checks = cur.fetchall()
            for elem in checks:
                desc = 'ChaseCheck '+str(elem[1])+': '+elem[2]
                sdict[elem[4].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[4].strftime('%m/%d')
                                                             +' b %-40s'%desc[:40]+' %10.2f'%elem[3]
                                                             +'%s'%('*' if elem[5] is None else ''))

            for key in sorted(sdict):
                f.write(sdict[key]+'\r\n')
            f.write('\r\n')

#
#
# M A I N  P R O G R A M
#
#

if len(sys.argv) > 1:
    year = sys.argv[1]
    yyyymm = year.split('-')

    # Set the year_has_month flag to True if month was entered along with the year
    if len(yyyymm) > 1:
        year_has_month = True
    else:
        year_has_month = False
else:
    print 'Usage '+sys.argv[0]+' yyyy[-mm]'
    sys.exit(1)

# Verify symbolic link to 'catfiles' is not broken
if os.path.isdir('catfiles'):
    if os.path.islink('catfiles') and not os.path.exists(os.readlink('catfiles')):
        print '"catfiles" is a broken symbolic link. Re-install vmware-tools:'
        print '1. cd /home/chrisanderson/Desktop/vmware-tools-distrib'
        print('2. "sudo perl vmware-install.pl" and enter password for chrisanderson')
        print '3. Answer all questions with the default (just hit <return>)'
        sys.exit(1)

if year_has_month:
    writeMonthText(yyyymm[0], yyyymm[1])
    writeMonthCsv(yyyymm[0], yyyymm[1])
else:
    for month in range(1, 13):
        writeMonthText(year, '%02d'%month)
        writeMonthCsv(year, '%02d'%month)
