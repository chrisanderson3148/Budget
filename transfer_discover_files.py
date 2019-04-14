import sys
import transferUtils


class Mixin(object):
    def read_monthly_discover_file(self, file_name, download=False):
        """Read in the downloaded Discover Card file line-by-line, and insert transactions in a
        dictionary.
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Discover Card download file
        :param bool download: whether or not to use different transaction date format
        :rtype: dict
        """
        '''
        There are two formats for Discover files, one for downloads, and the other for legacy monthly
        files
        '''
        #      0-2       3-5                6                                                          7        8
        # 2012,08,07,2012,08,07,PANANG THAI CUISINE LAFAYETTE CO,                                     -26,   Restaurants
        # 2007,10,16,2007,10,16,SAFEWAY STORE 1552 FORT COLLINS CO CASHOVER $ 20.00 PURCHASES $ 14.47,-34.47,Supermarkets
        #    tdate      xxxx              tpayee                                                       trans_amt_float  payee type
        #
        # example download file (note date format change and quotation marks):
        #      0         1                  2                                 3       4
        # 07/07/2015,07/07/2015,"MT RUSHMORE KOA/PALMER HILL CITY SD00797R",62.24,"Services"
        #    tdate                        tpayee                            trans_amt_float  payee type
        #
        # Discover card is the only one that does not use a unique identifier for every transaction. We
        # have to create one that is not fool-proof: combine the 2 dates, payee, amount, and payee type
        # with all the spaces removed. Most of the time the resulting string is unique. But once in a
        # while two or more transactions occur on the same day to the same payee for the same amount and
        # then they have to be distinguished. This is problematic.

        line_num = 0
        expected_fields = 5 if download else 9
        check_dict = {}
        output_dict = {}
        with open(file_name) as file_ptr:
            for line in file_ptr:
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines
                if line.startswith('<!--'):
                    self.logger.log('read_monthly_discover_file: Skipping line "' + line + '"')
                    continue

                # download files have header line; legacy monthly files do not
                if line_num == 0 and download:
                    # This is the file when there are no transactions in the given period
                    if line.startswith('There are no statements'):
                        return output_dict

                    fields = line.split(',')
                    if len(fields) != expected_fields:
                        self.logger.log('Discover download file header line has {} field(s) instead of '
                                        'expected {}'.format(len(fields), expected_fields))
                        sys.exit(1)
                    line_num += 1
                    continue
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines

                # Clear any commas inside quoted fields
                line = transferUtils.clear_commas_in_quotes(' ', line)

                # Look for in-line comments and keep them
                comment = ''
                idx = line.find('//')
                if idx >= 0:
                    comment = line[idx+2:]
                    line = line[:idx]

                # remove all double-quote characters (by this point it is guaranteed that there are no
                # extraneous commas)
                line = line.translate(None, '"')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields
                # (can be greater)
                if len(field) < expected_fields:
                    self.logger.log('Missing fields in file {}. Expected at least {} but got {}. '
                                    'Line:\n{}'.format(file_name, expected_fields, len(field), line))
                    sys.exit(1)

                # parse the first field -- transaction date
                if download:
                    trans_date = field[0]
                else:
                    trans_date = field[1]+'/'+field[2]+'/'+field[0]

                # parse the transaction amount
                # Discover reverses the sign of the amounts: no sign (positive)
                # for debits, - for credits -- we reverse it to preserve
                # consistency across accounts
                if download:
                    trans_amt_float = float(field[3])
                    trans_amt_string = '%.2f' % -trans_amt_float
                else:
                    trans_amt_float = float(field[7])
                    trans_amt_string = '%.2f' % trans_amt_float

                    # this converts amounts like '-7.1' to a consistent '-7.10'
                    field[7] = trans_amt_string

                # parse the transaction reference
                # some work here to get the dates in the right order and format
                if download:
                    date1 = field[0].split('/')
                    date2 = field[1].split('/')
                    trans_ref = ''.join([''.join([date1[2],
                                                  date1[0],
                                                  date1[1]]),
                                         ''.join([date2[2],
                                                  date2[0],
                                                  date2[1]]),
                                         field[2].replace(' ', ''),
                                         trans_amt_string,
                                         field[4].replace(' ', '')])
                else:
                    # The reference will be the entire line stripped of commas and spaces, minus any
                    # extra fields
                    trans_ref = ''.join(field[:expected_fields]).replace(' ', '')

                # check_dict is here to make sure the record reference is unique
                while trans_ref in check_dict:
                    self.logger.log('Discover transaction reference "{}" is not unique. '
                                    'Appending "x" to it'.format(trans_ref))
                    # If it's already being used, add a character to it
                    trans_ref = trans_ref + 'x'

                # now the reference is unique and can be inserted into the DATABASE
                check_dict[trans_ref] = 0

                # transaction payee
                if download:
                    trans_payee = field[2]
                else:
                    trans_payee = field[6]

                # Lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)
                self.logger.log('Discover transaction {} matches to category {}\n'.format(trans_payee,
                                                                                          bud_cat))

                # process the extra budget fields which may mean extra DATABASE records
                budget_category_dict = transferUtils.process_budget_fields(field[expected_fields:],
                                                                           trans_amt_string, bud_cat,
                                                                           trans_date, trans_ref)

                # insert the record(s) into the dictionary
                transferUtils.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date,
                                                     trans_payee, '', 'd', trans_amt_string, comment,
                                                     output_dict)
                line_num += 1
                # end for
        self.logger.log('read_monthly_discover_file processed {} records from {}\n'.
                        format(line_num-1, file_name))
        return output_dict

