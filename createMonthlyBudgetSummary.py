#!/usr/bin/python
"""Python executable script to create the monthly budget summary files"""

from __future__ import print_function
import sys
import os
import MySQLdb

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

# Open a connection to the DATABASE
DATABASE = MySQLdb.connect(host='localhost', user='root', passwd='sawtooth', db='officialBudget')
CURSOR = DATABASE.cursor()


def write_month_csv(my_year, my_month):
    """Write the CSV file with 'my_year' and 'my_month' part of the file name

    my_month is 1-based

    :param str my_year: the year as a string
    :param str my_month: the my_month name
    """
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # get the budget categories and sums for the time period from 'main'
    buds_summary = dict()
    CURSOR.execute("SELECT bud_category,sum(bud_amount) from main where bud_date between '"
                   + my_year + "-" + my_month + "-01' and '" + my_year + "-" + my_month
                   + "-31' and tran_checknum = '0' and tran_desc not like 'CHECK %' "
                   "group by bud_category order by bud_category;")

    rows = CURSOR.fetchall()
    # save results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL':
            key = 'COLLEGE'
        buds_summary[key] = row[1]

    # get the budget categories and sums for the time period from 'checks'
    CURSOR.execute("SELECT bud_cat,sum(bud_amt) from checks where bud_date between '" + my_year + "-"
                   + my_month + "-01' and '" + my_year + "-" + my_month + "-31' group by bud_cat;")
    rows = CURSOR.fetchall()
    # update results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL':
            key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]

    # get the budget categories and sums for the time period from 'chasechecks'
    CURSOR.execute("SELECT bud_cat,sum(bud_amt) from chasechecks where bud_date between '"
                   + my_year + "-" + my_month + "-01' and '" + my_year + "-" + my_month
                   + "-31' group by bud_cat;")
    rows = CURSOR.fetchall()
    # update results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL':
            key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]

    name = month_names[int(my_month) - 1] + ' ' + my_year

    # see if there are any results to save to the file
    if buds_summary:
        print('writeMonthlyCsv: No entries for my_month '+name)
        return
    else:
        print('writeMonthlyCsv: Month '+name+' has', len(buds_summary), 'entries')

    # write out to the file
    with open('catfiles/'+name.replace(' ', '')+'cat.csv', 'w') as file_ptr:
        file_ptr.write('Summary for '+name+'\r\n')
        for budget_category in sorted(buds_summary):
            file_ptr.write('%s,%.2f\r\n' % (budget_category, buds_summary[budget_category]))


def write_month_text(my_year, my_month):
    """Write the txt file with 'my_year' and 'my_month' part of the file name

    my_month is 1-based

    :param str my_year: the year as a string
    :param str my_month: the my_month name
    """
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # get the budget categories and sums for the time period from 'main'
    buds_summary = dict()
    CURSOR.execute("SELECT bud_category,sum(bud_amount) from main where bud_date between '"
                   + my_year + "-" + my_month + "-01' and '" + my_year + "-" + my_month
                   + "-31' and tran_checknum = '0' and tran_desc not like 'CHECK %' "
                   "group by bud_category order by bud_category;")
    rows = CURSOR.fetchall()

    # save results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL':
            key = 'COLLEGE'
        buds_summary[key] = row[1]

    # get the budget categories and sums for the time period from 'checks'
    CURSOR.execute("SELECT bud_cat,sum(bud_amt) from checks where bud_date between '" + my_year + "-"
                   + my_month + "-01' and '" + my_year + "-" + my_month + "-31' group by bud_cat;")
    rows = CURSOR.fetchall()

    # update the results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL':
            key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]

    # get the budget categories and sums for the time period from 'chasechecks'
    CURSOR.execute("SELECT bud_cat,sum(bud_amt) from chasechecks where bud_date between '"
                   + my_year + "-" + my_month + "-01' and '" + my_year + "-" + my_month
                   + "-31' group by bud_cat;")
    rows = CURSOR.fetchall()

    # update the results in dict
    for row in rows:
        key = row[0].rstrip().lstrip()
        if key == 'SCHOOL':
            key = 'COLLEGE'
        if key in buds_summary:
            buds_summary[key] += row[1]
        else:
            buds_summary[key] = row[1]

    name = month_names[int(my_month) - 1] + ' ' + my_year

    # see if there are any results to save to the file
    if not buds_summary:
        print('writeMonthlyText: No entries for my_month '+name)
        return
    else:
        print('writeMonthlyText: Month '+name+' has', len(buds_summary), 'entries')

    # write out to the file
    with open('catfiles/'+name.replace(' ', '')+'cat.txt', 'w') as file_ptr:
        file_ptr.write('Summary for '+name+'\r\n\r\n')

        # Now go through each budget category and print the individual transactions for each
        for budget_category in sorted(buds_summary):
            # print the summary line
            file_ptr.write('%-20s %10.2f\r\n' % (budget_category, buds_summary[budget_category]))

            # dictionary to store all the 'main' table results and uncleared check results for later
            # printing
            store_dict = dict()

            # select the 'main' table non-check (both Chase and CU) transactions that make up that
            # my_month/budget summary and store in dict
            if budget_category == 'COLLEGE':
                query = ("SELECT tran_ID,tran_date,tran_type,tran_desc,bud_amount FROM main WHERE "
                         "bud_date between '" + my_year + "-" + my_month + "-01' and '" + my_year + "-"
                         + my_month + "-31' and "
                         "(bud_category = 'COLLEGE' or bud_category = 'SCHOOL') and "
                         "tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;")
            else:
                query = ("SELECT tran_ID,tran_date,tran_type,tran_desc,bud_amount FROM main WHERE "
                         "bud_date between '" + my_year + "-" + my_month + "-01' and '" + my_year + "-"
                         + my_month + "-31' and bud_category = '" + budget_category
                         + "' and tran_checknum = '0' and tran_desc not like 'CHECK %' "
                         "order by bud_date;")
            CURSOR.execute(query)
            for elem in CURSOR:
                store_dict[elem[1].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[1].strftime('%m/%d')+' '
                                                                  + elem[2] + ' %-40s' % elem[3][:40]
                                                                  + ' %10.2f' % elem[4])

            # select the 'checks' table transactions that make up that
            # my_month/budget summary and store in dict
            if budget_category == 'COLLEGE':
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date,comments FROM checks "
                         "WHERE bud_date between '" + my_year + "-" + my_month + "-01' and '" + my_year
                         + "-" + my_month + "-31' and (bud_cat = 'COLLEGE' or bud_cat = 'SCHOOL') "
                         "order by tdate;")
            else:
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date,comments FROM checks "
                         "WHERE bud_date between '" + my_year + "-" + my_month + "-01' and '" + my_year
                         + "-" + my_month + "-31' and bud_cat = '" + budget_category
                         + "' order by tdate;")
            CURSOR.execute(query)
            checks = CURSOR.fetchall()
            for elem in checks:
                desc = ('Check '+str(elem[1])+': '+elem[2]+('|'+elem[6] if elem[6] else ''))
                store_dict[elem[4].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[4].strftime('%m/%d')
                                                                  + ' b %-40s' % desc[:40]
                                                                  + ' %10.2f' % elem[3]
                                                                  + '%s' % ('*' if elem[5] is None
                                                                            else ''))

            # select the 'chasechecks' table transactions that make up that my_month/budget summary and
            # store in dict
            if budget_category == 'COLLEGE':
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date FROM chasechecks WHERE "
                         "bud_date between '" + my_year + "-" + my_month + "-01' and '" + my_year + "-"
                         + my_month + "-31' and (bud_cat = 'COLLEGE' or bud_cat = 'SCHOOL') "
                         "order by tdate;")
            else:
                query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date FROM chasechecks WHERE "
                         "bud_date between '" + my_year + "-" + my_month + "-01' and '" + my_year + "-"
                         + my_month + "-31' and bud_cat = '" + budget_category + "' order by tdate;")
            CURSOR.execute(query)
            checks = CURSOR.fetchall()
            for elem in checks:
                desc = 'ChaseCheck '+str(elem[1])+': '+elem[2]
                store_dict[elem[4].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[4].strftime('%m/%d')
                                                                  + ' b %-40s' % desc[:40]
                                                                  + ' %10.2f' % elem[3]
                                                                  + '%s' % ('*' if elem[5] is None
                                                                            else ''))

            for key in sorted(store_dict):
                file_ptr.write(store_dict[key]+'\r\n')
            file_ptr.write('\r\n')

#
#
# M A I N  P R O G R A M
#
#

if len(sys.argv) > 1:
    YEAR = sys.argv[1]
    YYYYMM = YEAR.split('-')

    # Set the YEAR_HAS_MONTH flag to True if month was entered along with the year
    if len(YYYYMM) > 1:
        YEAR_HAS_MONTH = True
    else:
        YEAR_HAS_MONTH = False
else:
    print('Usage '+sys.argv[0]+' yyyy[-mm]')
    sys.exit(1)

# Verify symbolic link to 'catfiles' is not broken
if os.path.isdir('catfiles'):
    if os.path.islink('catfiles') and not os.path.exists(os.readlink('catfiles')):
        print('"catfiles" is a broken symbolic link. Re-install vmware-tools:')
        print('1. cd /home/chrisanderson/Desktop/vmware-tools-distrib')
        print('2. "sudo perl vmware-install.pl" and enter password for chrisanderson')
        print('3. Answer all questions with the default (just hit <return>)')
        sys.exit(1)

if YEAR_HAS_MONTH:
    write_month_text(YYYYMM[0], YYYYMM[1])
    write_month_csv(YYYYMM[0], YYYYMM[1])
else:
    for month in range(1, 13):
        write_month_text(YEAR, '%02d' % month)
        write_month_csv(YEAR, '%02d' % month)
