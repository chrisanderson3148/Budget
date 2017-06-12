import sys
import MySQLdb

class budgetDB(object):
    def __init__(self, host, user, passwd, db):
        # Open a connection to the database
        self.db = MySQLdb.connect(host=host, user=user, passwd=passwd, db=db)
        self.cur = self.db.cursor()
        self.cur2 = self.db.cursor()

        # Save the official list of column names for table main
        self.maincolumns = []
        self.cur.execute("select column_name from information_schema.columns where table_schema = 'officialBudget' and table_name='main';")
        for row in self.cur:
            self.maincolumns.append(row[0].upper())

        # Save the official list of column names for table checks
        self.checkscolumns = []
        self.cur.execute("select column_name from information_schema.columns where table_schema = 'officialBudget' and table_name='checks';")
        for row in self.cur:
            self.checkscolumns.append(row[0].upper())

        # Save the current list of all budget categories in table main 
        self.budcatlist = []
        self.cur.execute("select bud_category from main group by bud_category;")
        for row in self.cur:
            self.budcatlist.append(row[0].upper())

    def executeQuery(self, query):
        self.cur.execute(query)
        return self.cur

    def executeQuery2(self, query):
        self.cur2.execute(query)
        return self.cur2
