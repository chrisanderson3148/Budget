"""Module to handle the payee file"""

class TransferPayee(object):
    """Simple class definition"""

    def pretty(self, d, indent=0):
        """Recursive method to print contents of a dictionary
        
        :param dict d: dictionary to print
        :param int indent: number of spaces to indent each new level (default = 0)
        """
        for key, value in d.iteritems():
            # if indent == 0: print '\n'
            print '  ' * indent + str(key)
            if isinstance(value, dict):
                self.pretty(value, indent+1)
            else:
                print '  ' * (indent+1) + str(value)

    def writePayeeFile(self, plist, fname):
        """Write out the payee file to the named directory
        UNUSED
        
        :param list plist: the contents to write to the file, one entry per line
        :param str fname: the directory to put the file in
        """
        fname = fname + '/payee'
        with open(fname, 'w') as f:
            f.truncate()
            for row in plist:
                f.write('%-50s = %s\n' % (row[0], row[1]))
        print 'Wrote out file '+fname

    def readPayeeFile(self, fname):
        """Read the contents of the payee file and return results in a dictionary
        
        :param str fname: the name of the payee file
        :rtype: dict
        """
        outdict = dict()
        linenum = 0
        with open(fname) as f:
            for line in f:
                # Clean up line
                # The regexes sometimes contain the '\' character, which needs to be replaced with '\\'
                # because it's the escape character
                line = line.replace('\\', '\\\\')

                # strip leading and trailing blanks
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines
                if line.startswith('#'): continue # ignore comments
                if line.startswith('//'): continue # ignore comments

                field = line.split('=') # split line by '='

                # Parse the regex
                # set regex and strip any leading spaces
                regex = field[0].rstrip()

                # Parse the budget category
                budcat = field[1].lstrip()

                outdict[linenum] = [regex, budcat]
                linenum += 1
            f.close()
        print 'readPayeeFile processed', linenum, 'records'
        return outdict
