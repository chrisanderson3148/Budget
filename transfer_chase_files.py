import sys
import transferUtils
import transferFilesToDB


class ChaseMixin(object):

    def read_monthly_chase_file(self, file_name):
        """Read in the downloaded Chase Bank file line-by-line, and insert transactions in a dictionary.
        OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Chase Bank download file
        :rtype: dict
        """
        '''
          0            1                                     2                                       3
        CREDIT,20100216120000[0:GMT],"Online Transfer from  MMA XXXXXX6306 transaction#: 313944149",19.79
        DEBIT,20100212120000[0:GMT],"MCDONALD'S F109 BOULDER         02/11MCDONALD'",              -1.08
        CHECK,20100216120000[0:GMT],"CHECK 1108",                                                  -90.00
        trtype       tdatetime                           payee                                      tamt
        '''

        line_num = 0
        expected_fields = 4
        output_dict = dict()
        with open(file_name) as file_ptr:
            for line in file_ptr:
                line = line.strip()
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

                # split the line into fields (comma-separated)
                fields = line.split(',')

                # parse the date field -- transaction date
                trans_date = fields[1][4:6]+'/'+fields[1][6:8]+'/'+fields[1][0:4]

                # parse the transaction reference
                # The reference will be the entire line stripped of commas and spaces
                trans_ref = line.replace(',', '').replace(' ', '')

                # transaction amount
                trans_amt = fields[3]

                # transaction payee
                # strip out extra spaces
                trans_payee = ' '.join(fields[2].split())

                # Lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # process the extra budget fields which may mean extra DATABASE
                # records
                budget_category_dict = transferUtils.process_budget_fields(
                    fields[expected_fields:], trans_amt, bud_cat, trans_date, trans_ref)

                # insert the record(s) into the dictionary
                transferUtils.insert_entry_into_dict(
                    budget_category_dict, trans_ref, trans_date, trans_payee, '', 'c', trans_amt, comment, output_dict)
                line_num += 1
                # end for
        self.logger.log('read_monthly_chase_file processed {} records from {}\n'.
                        format(line_num, file_name))
        return output_dict

