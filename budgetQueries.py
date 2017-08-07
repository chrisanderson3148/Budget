"""Module to handle mySQL activities"""
import MySQLdb


class BudgetDB(object):
    """Class to handle DATABASE initialization and closing.

    :param str host: the name of the host of the DATABASE ('localhost' is likely)
    :param str user: the username to authenticate with the DATABASE
    :param str password: the password to authenticate with the DATABASE
    :param str db_name: the name of the mysql DATABASE.
    """
    def __init__(self, host, user, password, db_name):
        # Open a connection to the DATABASE
        self.db_connection = MySQLdb.connect(host=host, user=user, passwd=password, db=db_name)
        self.cursor = self.db_connection.cursor()
        self.cursor2 = self.db_connection.cursor()

        # Save the official list of column names for table main
        self.main_columns = []
        self.cursor.execute("select column_name from information_schema.columns where table_schema = "
                            "'officialBudget' and table_name='main';")
        for row in self.cursor:
            self.main_columns.append(row[0].upper())

        # Save the official list of column names for table checks
        self.checks_columns = []
        self.cursor.execute("select column_name from information_schema.columns where table_schema = "
                            "'officialBudget' and table_name='checks';")
        for row in self.cursor:
            self.checks_columns.append(row[0].upper())

        # Save the current list of all budget categories in table main
        self.bud_cat_list = []
        self.cursor.execute("select bud_category from main group by bud_category;")
        for row in self.cursor:
            self.bud_cat_list.append(row[0].upper())

    def __del__(self):
        """Gracefully shutdown the connection to the DATABASE."""
        self.cursor.close()
        self.cursor2.close()
        self.db_connection.close()
        print "Closed DATABASE connection"

    def execute_query(self, query):
        """Execute the query against the first DATABASE CURSOR

        :param str query: the query to execute
        :rtype: MySQLdb.cursors.Cursor
        """
        self.cursor.execute(query)
        return self.cursor

    def execute_query_2(self, query):
        """Execute the query against the alternate, extra DATABASE CURSOR

        :param str query: the query to execute
        :rtype: MySQLdb.cursors.Cursor
        """
        self.cursor2.execute(query)
        return self.cursor2
