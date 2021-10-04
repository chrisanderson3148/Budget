#!/usr/local/bin/python3
"""Python executable script to create the monthly budget summary files"""

from __future__ import print_function

import datetime
import sys
import os
import pymysql
from utils import Logger
import globals


class MonthlyBudgetSummaries(object):
    """
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
    """

    def __init__(self):
        # Open a connection to the DATABASE
        self.database = pymysql.connect(host='localhost', user='root', passwd=globals.DB_PASSWORD, db=globals.DB_NAME)
        self.db_cursor = self.database.cursor()
        self.logger = Logger('create_monthly_budget_summaries_log')

    def __del__(self):
        self.database.close()

    def write_month_csv(self, my_year, my_month):
        """Write the CSV file with 'my_year' and 'my_month' part of the file name

        my_month is 1-based

        :param str my_year: the year as a string
        :param str my_month: the my_month name
        """
        start = datetime.datetime.now()
        month_num = int(my_month) - 1
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        dayfirst = f"{my_year}-{my_month}-01"
        if int(my_year) % 400 == 0 or (int(my_year) % 100 != 0 and int(my_year) % 4 == 0):
            month_days[1] = 29
        daylast = f"{my_year}-{my_month}-{month_days[month_num]}"

        # get the budget categories and sums for the time period from 'main'
        buds_summary = dict()
        my_query = ("SELECT bud_category,sum(bud_amount) from main where "
                    f"bud_date between '{dayfirst}' and '{daylast}' and tran_checknum = '0' and "
                    "tran_desc not like 'CHECK %' group by bud_category order by bud_category;")
        self.db_cursor.execute(my_query)

        rows = self.db_cursor.fetchall()
        # save results in dict
        for row in rows:
            key = row[0].strip()
            if key == 'SCHOOL':
                key = 'COLLEGE'
            buds_summary[key] = row[1]

        # get the budget categories and sums for the time period from 'checks'
        my_query = (f"SELECT bud_cat,sum(bud_amt) from checks where bud_date between '{dayfirst}' and '{daylast}' "
                    "group by bud_cat;")
        self.db_cursor.execute(my_query)
        rows = self.db_cursor.fetchall()

        # update results in dict
        for row in rows:
            key = row[0].strip()
            if key == 'SCHOOL':
                key = 'COLLEGE'
            if key in buds_summary:
                buds_summary[key] += row[1]
            else:
                buds_summary[key] = row[1]

        name = month_names[int(my_month) - 1] + ' ' + my_year

        # see if there are any results to save to the file
        et = datetime.datetime.now() - start
        if not buds_summary:
            self.logger.log(f"writeMonthlyCsv: No entries for my_month {name} ({et.total_seconds():.2f}s)")
            return

        # write out to the file
        with open('catfiles/'+name.replace(' ', '')+'cat.csv', 'w') as file_ptr:
            file_ptr.write('Summary for '+name+'\r\n')
            for budget_category in sorted(buds_summary):
                file_ptr.write('%s,%.2f\r\n' % (budget_category, buds_summary[budget_category]))
        et = datetime.datetime.now() - start
        self.logger.log(f"writeMonthlyCsv: Month {name} has {len(buds_summary)} entries ({et.total_seconds():.2f}s)")

    def write_month_text_few_queries(self, my_year, my_month):
        """Write the txt file with 'my_year' and 'my_month' part of the file name

        Use only 2 DB queries. Figure out the rest from the data returned from them.
        my_month is 1-based

        :param str my_year: the year as a string
        :param str my_month: the my_month name
        """

        start = datetime.datetime.now()
        month_num = int(my_month) - 1
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month = f"{my_year}-{my_month}-%"

        # get all the records for the given month from main, ordered by category and date
        buds_summary = dict()
        self.db_cursor.execute(f"SELECT * from main where bud_date like '{month}' and tran_checknum = '0' and "
                               "tran_desc not like 'CHECK %' order by bud_category,bud_date;")
        main = self.db_cursor.fetchall()

        # get the budget categories and sums for the time period from 'main'
        #     0         1       2           3           4          5           6            7        8        9
        # tran_date,tran_ID,tran_desc,tran_checknum,tran_type,tran_amount,bud_category,bud_amount,bud_date,comment
        key = ""
        sum = 0.0
        for row in main:
            if key == "":
                key = row[6].strip()
                sum = float(row[7])
            elif key != row[6].strip():
                if key == 'SCHOOL':
                    key = 'COLLEGE'
                buds_summary[key] = sum
                key = row[6].strip()
                sum = float(row[7])
            else:
                sum += float(row[7])
        # take care of last key which hasn't been added to buds_summary yet
        if key != "":
            if key == 'SCHOOL':
                key = 'COLLEGE'
            buds_summary[key] = sum

        # get all the records for the given month from checks, ordered by category and date
        self.db_cursor.execute(f"SELECT * from checks where bud_date like '{month}' order by bud_cat,bud_date;")
        checks = self.db_cursor.fetchall()

        # get the budget categories and sums for the time period from 'checks'
        #   0      1       2    3      4      5       6       7        8         9
        # tnum,tchecknum,tamt,tdate,tpayee,bud_cat,bud_amt,bud_date,comments,clear_date
        key = ""
        sum = 0.0
        for row in checks:
            if key == "":
                key = row[5].strip()
                sum = float(row[6])
            elif key != row[5].strip():
                if key == 'SCHOOL':
                    key = 'COLLEGE'
                if key in buds_summary:
                    buds_summary[key] += sum
                else:
                    buds_summary[key] = sum
                key = row[5].strip()
                sum = float(row[6])
            else:
                sum += float(row[6])
        # take care of last key which hasn't been added to buds_summary yet
        if key != "":
            if key == 'SCHOOL':
                key = 'COLLEGE'
            if key in buds_summary:
                buds_summary[key] += sum
            else:
                buds_summary[key] = sum

        name = month_names[month_num] + ' ' + my_year

        # see if there are any results to save to the file
        et = datetime.datetime.now() - start
        if not buds_summary:
            self.logger.log(f"writeMonthlyText: No entries for my_month {name} ({et.total_seconds():.2f}s)")
            return

        # write out to the file
        with open(f"catfiles/{name.replace(' ', '')}cat.txt", "w") as file_ptr:
            file_ptr.write(f"Summary for {name}\r\n\r\n")
            # main database indices
            tdate = 0
            tid = 1
            tdesc = 2
            ttype = 4
            bcat = 6
            bamt = 7

            # checks database indices
            tnum = 0
            tcknum = 1
            tckdate = 3
            tckpayee = 4
            bckcat = 5
            bckamt = 6
            ckcomm = 8
            clrdate = 9

            # Now go through each budget category and print the individual transactions for each
            for budget_category in sorted(buds_summary):
                # print the summary line
                file_ptr.write(f"{budget_category:<20s} {buds_summary[budget_category]:10.2f}\r\n")

                # dictionary to store all the 'main' table results and uncleared check results for later printing
                budcat_store_dict = dict()

                for elem in main:
                    if elem[bcat] == budget_category:
                        key = f"{elem[tdate].strftime('%Y%m%d')}{elem[tid]}"
                        budcat_store_dict[key] = (f"\t{elem[tdate].strftime('%m/%d')} {elem[ttype]} "
                                                  f"{elem[tdesc][:40]:<40s} {elem[bamt]:10.2f}")

                for elem in checks:
                    if elem[bckcat] == budget_category:
                        desc = f"Check {elem[tcknum]}: {elem[tckpayee]}{(f'|{elem[ckcomm]}' if elem[ckcomm] else '')}"
                        key = f"{elem[tckdate].strftime('%Y%m%d')}{elem[tnum]}"
                        budcat_store_dict[key] = (f"\t{elem[tckdate].strftime('%m/%d')} b {desc[:40]:<40s} "
                                                  f"{elem[bckamt]:10.2f}{('*' if elem[clrdate] is None else '')}")

                for key in sorted(budcat_store_dict):
                    file_ptr.write(budcat_store_dict[key] + '\r\n')
                file_ptr.write('\r\n')  # write a blank line at the end of each budget category section
        et = datetime.datetime.now() - start
        self.logger.log(f"writeMonthlyText: Month {name} has {len(buds_summary)} entries ({et.total_seconds():.2f}s)")

    def write_month_text(self, my_year, my_month):
        """Write the txt file with 'my_year' and 'my_month' part of the file name

        my_month is 1-based

        :param str my_year: the year as a string
        :param str my_month: the my_month name
        """
        start = datetime.datetime.now()
        month_num = int(my_month) - 1
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        dayfirst = f"{my_year}-{my_month}-01"
        if int(my_year) % 400 == 0 or (int(my_year) % 100 != 0 and int(my_year) % 4 == 0):
            month_days[1] = 29
        daylast = f"{my_year}-{my_month}-{month_days[month_num]}"

        # get the budget categories and sums for the time period from 'main'
        buds_summary = dict()
        self.db_cursor.execute(f"SELECT bud_category,sum(bud_amount) from main where "
                               f"bud_date between '{dayfirst}' and '{daylast}' and "
                               "tran_checknum = '0' and tran_desc not like 'CHECK %' "
                               "group by bud_category order by bud_category;")
        rows = self.db_cursor.fetchall()

        # save results in dict
        for row in rows:
            key = row[0].strip()
            if key == 'SCHOOL':
                key = 'COLLEGE'
            buds_summary[key] = row[1]

        # get the budget categories and sums for the time period from 'checks'
        self.db_cursor.execute(f"SELECT bud_cat,sum(bud_amt) from checks where "
                               f"bud_date between '{dayfirst}' and '{daylast}' group by bud_cat;")
        rows = self.db_cursor.fetchall()

        # update the results in dict
        for row in rows:
            key = row[0].strip()
            if key == 'SCHOOL':
                key = 'COLLEGE'
            if key in buds_summary:
                buds_summary[key] += row[1]
            else:
                buds_summary[key] = row[1]

        name = month_names[month_num] + ' ' + my_year

        # see if there are any results to save to the file
        et = datetime.datetime.now() - start
        if not buds_summary:
            self.logger.log(f"writeMonthlyText: No entries for my_month {name} ({et.total_seconds():.2f}s)")
            return

        # write out to the file
        with open('catfiles/' + name.replace(' ', '') + 'cat_manyq.txt', 'w') as file_ptr:
            file_ptr.write('Summary for ' + name + '\r\n\r\n')

            # Now go through each budget category and print the individual transactions for each
            for budget_category in sorted(buds_summary):
                # print the summary line
                file_ptr.write('%-20s %10.2f\r\n' % (budget_category, buds_summary[budget_category]))

                # dictionary to store all the 'main' table results and uncleared check results for later
                # printing
                store_dict = dict()

                # select the 'main' table non-check transactions that make up my_month/budget summary and store in dict
                if budget_category == 'COLLEGE':
                    query = ("SELECT tran_ID,tran_date,tran_type,tran_desc,bud_amount FROM main WHERE "
                             f"bud_date between '{dayfirst}' and '{daylast}' and "
                             "(bud_category = 'COLLEGE' or bud_category = 'SCHOOL') and "
                             "tran_checknum = '0' and tran_desc not like 'CHECK %' order by bud_date;")
                else:
                    query = ("SELECT tran_ID,tran_date,tran_type,tran_desc,bud_amount FROM main WHERE "
                             f"bud_date between '{dayfirst}' and '{daylast}' and "
                             f"bud_category = '{budget_category}' and tran_checknum = '0' and "
                             f"tran_desc not like 'CHECK %' order by bud_date;")
                self.db_cursor.execute(query)
                for elem in self.db_cursor:
                    store_dict[elem[1].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[1].strftime('%m/%d')+' '
                                                                      + elem[2] + ' %-40s' % elem[3][:40]
                                                                      + ' %10.2f' % elem[4])

                # select the 'checks' table transactions that make up that my_month/budget summary and store in dict
                if budget_category == 'COLLEGE':
                    query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date,comments FROM checks WHERE "
                             f"bud_date between '{dayfirst}' and '{daylast}' and "
                             "(bud_cat = 'COLLEGE' or bud_cat = 'SCHOOL') order by tdate;")
                else:
                    query = ("SELECT tnum,tchecknum,tpayee,bud_amt,tdate,clear_date,comments FROM checks WHERE "
                             f"bud_date between '{dayfirst}' and '{daylast}' and bud_cat = '{budget_category}' "
                             f"order by tdate;")
                self.db_cursor.execute(query)
                checks = self.db_cursor.fetchall()
                for elem in checks:
                    desc = ('Check '+str(elem[1])+': '+elem[2]+('|'+elem[6] if elem[6] else ''))
                    store_dict[elem[4].strftime('%Y%m%d')+elem[0]] = ('\t'+elem[4].strftime('%m/%d')
                                                                      + ' b %-40s' % desc[:40]
                                                                      + ' %10.2f' % elem[3]
                                                                      + '%s' % ('*' if elem[5] is None
                                                                                else ''))

                for key in sorted(store_dict):
                    file_ptr.write(store_dict[key]+'\r\n')
                file_ptr.write('\r\n')
        et = datetime.datetime.now() - start
        self.logger.log(f"writeMonthlyText: Month {name} has {len(buds_summary)} entries ({et.total_seconds():.2f}s)")

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
    print(f"Usage {sys.argv[0]} yyyy[-mm]")
    sys.exit(1)

# Verify symbolic link to 'catfiles' is not broken
if os.path.isdir('catfiles'):
    if os.path.islink('catfiles') and not os.path.exists(os.readlink('catfiles')):
        print('"catfiles" is a broken symbolic link. Re-install vmware-tools:')
        print('1. cd /home/chrisanderson/Desktop/vmware-tools-distrib')
        print('2. "sudo perl vmware-install.pl" and enter password for chrisanderson')
        print('3. Answer all questions with the default (just hit <return>)')
        sys.exit(1)

create = MonthlyBudgetSummaries()

if YEAR_HAS_MONTH:
    # create.write_month_text(YYYYMM[0], YYYYMM[1])
    create.write_month_text_few_queries(YYYYMM[0], YYYYMM[1])
    create.write_month_csv(YYYYMM[0], YYYYMM[1])
else:
    for month in range(1, 13):
        # create.write_month_text(YEAR, f'{month:02d}')
        create.write_month_text_few_queries(YEAR, f'{month:02d}')
        create.write_month_csv(YEAR, f'{month:02d}')
