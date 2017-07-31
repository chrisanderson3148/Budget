"""Module to handle the payee file"""


class TransferPayee(object):
    """Simple class definition"""

    def pretty(self, the_dict, indent=0):
        """Recursive method to print contents of a dictionary

        :param dict the_dict: dictionary to print
        :param int indent: number of spaces to indent each new level (default = 0)
        """
        for key, value in the_dict.iteritems():
            # if indent == 0: print '\n'
            print '  ' * indent + str(key)
            if isinstance(value, dict):
                self.pretty(value, indent+1)
            else:
                print '  ' * (indent+1) + str(value)

    def write_payee_file(self, plist, file_name):
        """Write out the payee file to the named directory
        UNUSED

        :param list plist: the contents to write to the file, one entry per line
        :param str file_name: the directory to put the file in
        """
        file_name = file_name + '/payee'
        with open(file_name, 'w') as f_ptr:
            f_ptr.truncate()
            for row in plist:
                f_ptr.write('%-50s = %s\n' % (row[0], row[1]))
        print 'Wrote out file ' + file_name

    def read_payee_file(self, file_name):
        """Read the contents of the payee file and return results in a dictionary

        :param str file_name: the name of the payee file
        :rtype: dict
        """
        out_dict = dict()
        line_num = 0
        with open(file_name) as f_ptr:
            for line in f_ptr:
                # Clean up line
                # The regexes sometimes contain the '\' character, which needs to be replaced with '\\'
                # because it's the escape character
                line = line.replace('\\', '\\\\')

                # strip leading and trailing blanks
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines
                if line.startswith('#'):
                    continue  # ignore comments
                if line.startswith('//'):
                    continue  # ignore comments

                field = line.split('=')  # split line by '='

                # Parse the regex
                # set regex and strip any leading spaces
                regex = field[0].rstrip()

                # Parse the budget category
                budget_category = field[1].lstrip()

                out_dict[line_num] = [regex, budget_category]
                line_num += 1
            f_ptr.close()
        print 'readPayeeFile processed', line_num, 'records'
        return out_dict
