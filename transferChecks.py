#!/usr/bin/python

import os, sys
import collections

class TransferChecks(object):

    def pretty(self, d, indent=0):
        for key, value in d.iteritems():
            # if indent == 0: print '\n'
            print '  ' * indent + str(key)
            if isinstance(value, dict):
                pretty(value, indent+1)
            else:
                print '  ' * (indent+1) + str(value)

    def processBudcat(self, fieldInfo, dt):
        return fieldInfo, dt

    def writeChecksFile(self, chkslist, fname):
        fname = fname+'/checks'
        with open(fname, 'w') as f:
            f.truncate()
            for row in chkslist:
                if row[1] is None and row[2] is None and not row[3] and not row[4]:
                    f.write('%7d%s\n' % (row[0], ' # %s' % row[6] if row[6] else ''))
                else:
                    f.write('%7d%11s|%s|%s%s%s\n' % (row[0], '%11.2f' % row[1] if row[1] is not None else '', row[2].strftime('%m/%d/%Y') if row[2] is not None else '', row[3], '|%s' % row[4] if row[4] and row[4] != 'UNKNOWN' else '', ' # %s' % row[6] if row[6] else ''))
        print 'Wrote out file '+fname

    def parseBudgetFields(self, extfield):
        '''
        Each field in extfield can be like: 'BUDCAT[=BUDAMT[=BUDDATE]]', or 'DATE=<BUDDATE>'
        '''
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
        outdict = dict()
        transactions = 0
        linenum = 0
        with open(fname) as f:
            for line in f:
                # Clean up line
                line = line.rstrip().lstrip() # strip leading and trailing blanks
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
                comment = comment.translate(None, '"') # remove all double-quote characters

                # Parse line
                if len(line) < 7:
                    checknum = line.strip() # check number but nothing else
                    outdict[checknum] = [checknum, '', '', '', '', '', '', comment]
                    linenum += 1
                    continue
                checknum = line[:6].strip() # other info after check number
                field = line[6:].split('|') # split line part after check number into fields delimited by '|'
                amt = field[0].strip() # set amt and strip any leading spaces

                # Parse the date
                if len(field) > 1: # if there are 2 or more fields, set the date
                    date = field[1].strip()
                else:
                    date = ''

                # Parse the payee
                if len(field) > 2: # if there are 3 or more fields, set the payee
                    payee = field[2]
                else:
                    payee = ''

                # Parse the budget category
                buddict = self.parseBudgetFields(field[3:])

                # finish processing them
                tran_amt_isneg = amt.startswith('-')
                remainder = abs(float(amt)) # remainder is a double and is always POSITIVE
                for key, val in collections.OrderedDict(sorted(buddict.items())).iteritems(): 
                    if not val[0]:
                        buddict[key][0] = 'UNKNOWN' # default
                    # The assumption is that all budget amounts are positive, but use the same sign as the transaction amount
                    if not val[1]: # no budget amount?
                        buddict[key][1] = '%.2f' % (-1.0*remainder if tran_amt_isneg else remainder) # assign any remainder to it
                        # print 'Assigned '+bcaddict[key][1]+' to bud_amt -- tran_amt_isneg=',tran_amt_isneg
                        remainder = 0.0
                    else: # otherwise decrement remainder by the budget amount
                        remainder = remainder - float(val[1]) # keep track of the remainder
                        if tran_amt_isneg and not buddict[key][1].startswith('-'):
                            buddict[key][1] = '-'+buddict[key][1]
                        if remainder < 0.0: # something didn't add up
                            remainder = 0.0
                            print 'Calculating amount for',val,'and got a remainder less than zero (tid='+field[itid]+', extra fields='+','.join(field[expfields:])+')'
                    if not val[2]: # no budget date?
                        buddict[key][2] = date # assign transaction date

                if len(buddict) == 1: #      0      1     2     3       4cat            5amt           6date         7
                    outdict[checknum] = [checknum, amt, date, payee, buddict[0][0], buddict[0][1], buddict[0][2], comment]
                else:
                    keyprefix = checknum
                    # print 'Multiline transaction: '+checknum,buddict
                    for key, bud in collections.OrderedDict(sorted(buddict.items())).iteritems():
                        mykey = keyprefix + '-' + str(key)
                        # print mykey, checknum, amt, date, payee, bud[0], bud[1], bud[2], comment
                        #                    0       1    2      3     4cat     5amt   6date     7
                        outdict[mykey] = [checknum, amt, date, payee, bud[0], bud[1], bud[2], comment]
                        transactions += 1
                linenum += 1
            f.close()
        print 'readChecksFile processed',linenum,'records from '+fname
        return outdict

