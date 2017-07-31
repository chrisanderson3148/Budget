"""Module to handle checks transfer"""
from __future__ import print_function
import collections


class TransferChecks(object):
    """Manages transfer of check information"""

    def pretty(self, the_dict, indent=0):
        """Recursively pretty prints the dictionary 'd'

        :param dict the_dict: the dictionary to print
        :param int indent: the indent to use for each level (default to 0)
        """
        for key, value in the_dict.iteritems():
            print('  ' * indent + str(key))
            if isinstance(value, dict):
                self.pretty(value, indent+1)
            else:
                print('  ' * (indent+1) + str(value))

    def write_checks_file(self, checks_list, file_name):
        """Writes out the checks file
        UNUSED

        :param list checks_list: the list of checks
        :param str file_name: the file name
        """
        file_name = file_name + '/checks'
        with open(file_name, 'w') as file_ptr:
            file_ptr.truncate()
            for row in checks_list:
                if row[1] is None and row[2] is None and not row[3] and not row[4]:
                    file_ptr.write('%7d%s\n' % (row[0], ' # %s' % row[6] if row[6] else ''))
                else:
                    file_ptr.write('%7d%11s|%s|%s%s%s\n' % (row[0], '%11.2f' % row[1] if row[1] else '',
                                                            row[2].strftime('%m/%d/%Y') if row[2]
                                                            else '',
                                                            row[3],
                                                            '|%s' % row[4]
                                                            if row[4] and row[4] != 'UNKNOWN' else '',
                                                            ' # %s' % row[6] if row[6] else ''))
        print('Wrote out file ' + file_name)

    def parse_budget_fields(self, extra_field):
        """Parse the budget fields

        Each field in extfield can be like:
        'BUDCAT[=BUDAMT[=BUDDATE]]', or
        'DATE=<BUDDATE>'

        :param str extra_field:
        """
        bud_cat = ''
        bud_amt = ''
        bud_date = ''
        idx = 0
        arr = {}
        for field in extra_field:
            subfield = field.split('=')
            if subfield[0] == 'DATE':
                if bud_date:
                    arr[idx] = [bud_cat, bud_amt, bud_date]
                    bud_cat = ''
                    bud_amt = ''
                    bud_date = ''
                    idx += 1
                else:
                    bud_date = subfield[1]
            else:
                if bud_cat:
                    arr[idx] = [bud_cat, bud_amt, bud_date]
                    bud_amt = ''
                    bud_date = ''
                    idx += 1
                if len(subfield) == 1:
                    bud_cat = subfield[0]
                elif len(subfield) == 2:
                    bud_cat = subfield[0]
                    bud_amt = subfield[1]
                else:
                    bud_cat = subfield[0]
                    bud_amt = subfield[1]
                    bud_date = subfield[2]

        # assign the last or only row
        arr[idx] = [bud_cat, bud_amt, bud_date]
        return arr

    def read_checks_file(self, file_name):
        """Read in the named checks file

        :param str file_name: the name of the checks file to read in
        """
        out_dict = dict()
        transactions = 0
        line_num = 0
        with open(file_name) as file_ptr:
            for line in file_ptr:
                # Clean up line
                # strip leading and trailing blanks
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines
                if line.startswith('#'):
                    continue  # ignore full-line comments
                if line.startswith('//'):
                    continue  # ignore full-line comments
                comment = ''
                idx = line.find('#')
                if idx >= 0:
                    comment = line[idx+1:].lstrip()
                    line = line[:idx]  # strip off any comments
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:].lstrip()
                    line = line[:idx]  # strip off any comments

                # remove all double-quote characters
                comment = comment.translate(None, '"')

                # Parse line
                if len(line) < 7:
                    check_num = line.strip()  # check number but nothing else
                    out_dict[check_num] = [check_num, '', '', '', '', '', '', comment]
                    line_num += 1
                    continue
                check_num = line[:6].strip()  # other info after check number

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
                bud_dict = self.parse_budget_fields(field[3:])

                # finish processing them
                trans_amt_is_neg = amt.startswith('-')

                # remainder is a double and is always POSITIVE
                remainder = abs(float(amt))
                for key, val in collections.OrderedDict(sorted(bud_dict.items())).iteritems():
                    if not val[0]:
                        bud_dict[key][0] = 'UNKNOWN'  # default

                    # The assumption is that all budget amounts are positive, but use the same sign as
                    # the transaction amount
                    if not val[1]:  # no budget amount?

                        # assign any remainder to it
                        bud_dict[key][1] = '%.2f' % (-1.0*remainder if trans_amt_is_neg else remainder)

                        remainder = 0.0
                    else:  # otherwise decrement remainder by the budget amount
                        # keep track of the remainder
                        remainder = remainder - float(val[1])
                        if trans_amt_is_neg and not bud_dict[key][1].startswith('-'):
                            bud_dict[key][1] = '-'+bud_dict[key][1]
                        if remainder < 0.0:  # something didn't add up
                            remainder = 0.0
                            print('Calculating amount for {} and got a remainder less than zero.'
                                  .format(val))
                    if not val[2]:  # no budget date?
                        bud_dict[key][2] = date  # assign transaction date

                if len(bud_dict) == 1:
                    out_dict[check_num] = [check_num, amt, date, payee,
                                           bud_dict[0][0], bud_dict[0][1], bud_dict[0][2], comment]
                else:
                    key_prefix = check_num
                    for key, bud in collections.OrderedDict(sorted(bud_dict.items())).iteritems():
                        my_key = key_prefix + '-' + str(key)
                        out_dict[my_key] = [check_num, amt, date, payee, bud[0], bud[1], bud[2], comment]
                        transactions += 1
                line_num += 1
            file_ptr.close()

        print('read_checks_file processed', line_num, 'records from ' + file_name)

        return out_dict
