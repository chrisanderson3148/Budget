import sys
import transferUtils


class Mixin(object):
    def read_monthly_amex_file(self, file_name):
        """Read in the downloaded American Express file line-by-line, and insert transactions in a
        dictionary. OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the American Express download file
        :rtype: dict
        """
        line_num = 0
        expected_fields = 5
        output_dict = {}
        with open(file_name) as file_ptr:
            for line in file_ptr:
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

                # remove all double-quote characters (by this point it is
                # guaranteed that there are no extraneous commas)
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
                trans_date = field[0]  # mm/dd/yyyy

                # parse the transaction reference
                trans_ref = field[1].split()[1]

                # transaction amount
                trans_amt = field[2]

                # transaction payee
                trans_payee = field[3]

                # Lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # process the extra budget fields which may mean extra DATABASE
                # records
                budget_category_dict = transferUtils.process_budget_fields(field[expected_fields:],
                                                                           trans_amt, bud_cat,
                                                                           trans_date, trans_ref)

                # insert the record(s) into the dictionary
                transferUtils.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date,
                                                     trans_payee, '', 'x', trans_amt, comment,
                                                     output_dict)
                line_num += 1
                # end for
        self.logger.log('read_monthly_amex_file processed {} records from {}\n'.
                        format(line_num, file_name))
        return output_dict


