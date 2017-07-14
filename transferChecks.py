import collections


class TransferChecks(object):
    """Manages transfer of check information"""

    def pretty(self, d, indent=0):
        """Recursively pretty prints the dictionary 'd'
        
        :param dict d: the dictionary to print
        :param int indent: the indent to use for each level (default to 0)
        """
        for key, value in d.iteritems():
            # if indent == 0: print '\n'
            print '  ' * indent + str(key)
            if isinstance(value, dict):
                self.pretty(value, indent+1)
            else:
                print '  ' * (indent+1) + str(value)

    def writeChecksFile(self, chkslist, fname):
        """Writes out the checks file
        UNUSED
        
        :param list chkslist: the list of checks
        :param str fname: the file name
        """
        fname = fname+'/checks'
        with open(fname, 'w') as f:
            f.truncate()
            for row in chkslist:
                if row[1] is None and row[2] is None and not row[3] and not row[4]:
                    f.write('%7d%s\n' % (row[0], ' # %s' % row[6] if row[6] else ''))
                else:
                    f.write('%7d%11s|%s|%s%s%s\n' % (row[0], '%11.2f' % row[1]
                            if row[1] is not None else '', row[2].strftime('%m/%d/%Y')
                            if row[2] is not None else '', row[3], '|%s' % row[4]
                            if row[4] and row[4] != 'UNKNOWN' else '',
                            ' # %s' % row[6] if row[6] else ''))
        print 'Wrote out file '+fname

    def parseBudgetFields(self, extfield):
        """Parse the budget fields
        
        Each field in extfield can be like:
        'BUDCAT[=BUDAMT[=BUDDATE]]', or
        'DATE=<BUDDATE>'
        
        :param str extfield: 
        """
        budcat = ''
        budamt = ''
        buddat = ''
        idx = 0
        arr = {}
        for field in extfield:
            subfield = field.split('=')
            if subfield[0] == 'DATE':
                if buddat:
                    arr[idx] = [budcat, budamt, buddat]
                    budcat = ''
                    budamt = ''
                    buddat = ''
                    idx += 1
                else:
                    buddat = subfield[1]
            else:
                if budcat:
                    arr[idx] = [budcat, budamt, buddat]
                    budcat = ''
                    budamt = ''
                    buddat = ''
                    idx += 1
                if len(subfield) == 1:
                    budcat = subfield[0]
                elif len(subfield) == 2:
                    budcat = subfield[0]
                    budamt = subfield[1]
                else:
                    budcat = subfield[0]
                    budamt = subfield[1]
                    buddat = subfield[2]

        # assign the last or only row
        arr[idx] = [budcat, budamt, buddat]
        return arr

    def readChecksFile(self, fname):
        """Read in the named checks file
        
        :param str fname: the name of the checks file to read in
        """
        outdict = dict()
        transactions = 0
        linenum = 0
        with open(fname) as f:
            for line in f:
                # Clean up line
                # strip leading and trailing blanks
                line = line.rstrip().lstrip()
                if not line: continue # ignore blank lines
                if line.startswith('#'): continue # ignore full-line comments
                if line.startswith('//'): continue # ignore full-line comments
                comment = ''
                idx = line.find('#')
                if idx >= 0:
                    comment = line[idx+1:].lstrip()
                    line = line[:idx] # strip off any comments
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:].lstrip()
                    line = line[:idx] # strip off any comments

                # remove all double-quote characters
                comment = comment.translate(None, '"')

                # Parse line
                if len(line) < 7:
                    checknum = line.strip() # check number but nothing else
                    outdict[checknum] = [checknum, '', '', '', '', '', '', comment]
                    linenum += 1
                    continue
                checknum = line[:6].strip() # other info after check number

                # split line part after check number into fields delimited by '|'
                field = line[6:].split('|')

                # set amt and strip any leading spaces
                amt = field[0].strip()

                # Parse the date
                if len(field) > 1: # if there are 2 or more fields, set the date
                    date = field[1].strip()
                else:
                    date = ''

                # Parse the payee
                # if there are 3 or more fields, set the payee
                if len(field) > 2:
                    payee = field[2]
                else:
                    payee = ''

                # Parse the budget category
                buddict = self.parseBudgetFields(field[3:])

                # finish processing them
                tran_amt_isneg = amt.startswith('-')

                # remainder is a double and is always POSITIVE
                remainder = abs(float(amt))
                for key, val in collections.OrderedDict(sorted(buddict.items())).iteritems():
                    if not val[0]:
                        buddict[key][0] = 'UNKNOWN' # default

                    # The assumption is that all budget amounts are positive, but use the same sign as
                    # the transaction amount
                    if not val[1]: # no budget amount?

                        # assign any remainder to it
                        buddict[key][1] = '%.2f' % (-1.0*remainder if tran_amt_isneg else remainder)

                        remainder = 0.0
                    else: # otherwise decrement remainder by the budget amount
                        # keep track of the remainder
                        remainder = remainder - float(val[1])
                        if tran_amt_isneg and not buddict[key][1].startswith('-'):
                            buddict[key][1] = '-'+buddict[key][1]
                        if remainder < 0.0: # something didn't add up
                            remainder = 0.0
                            print('Calculating amount for', val, 'and got a remainder less than zero '
                                  '(tid='+field[itid]+', extra fields='+','.join(field[expfields:])+')')
                    if not val[2]: # no budget date?
                        buddict[key][2] = date # assign transaction date

                if len(buddict) == 1:
                    outdict[checknum] = [checknum, amt, date, payee,
                                         buddict[0][0], buddict[0][1], buddict[0][2], comment]
                else:
                    keyprefix = checknum
                    # print 'Multiline transaction: '+checknum,buddict
                    for key, bud in collections.OrderedDict(sorted(buddict.items())).iteritems():
                        mykey = keyprefix + '-' + str(key)
                        outdict[mykey] = [checknum, amt, date, payee, bud[0], bud[1], bud[2], comment]
                        transactions += 1
                linenum += 1
            f.close()
        print 'readChecksFile processed', linenum, 'records from '+fname
        return outdict
