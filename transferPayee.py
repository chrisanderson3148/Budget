#!/usr/bin/python

import os, sys
import collections

class TransferPayee(object):

    def pretty(self, d, indent=0):
        for key, value in d.iteritems():
            # if indent == 0: print '\n'
            print '  ' * indent + str(key)
            if isinstance(value, dict):
                pretty(value, indent+1)
            else:
                print '  ' * (indent+1) + str(value)

    def writePayeeFile(self, plist, fname):
        fname = fname + '/payee'
        with open(fname, 'w') as f:
            f.truncate()
            for row in plist:
                f.write('%-50s = %s\n' % (row[0], row[1]))
        print 'Wrote out file '+fname

    def readPayeeFile(self, fname):
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
