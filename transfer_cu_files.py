import sys
import transferUtils

from os import path


class Mixin(object):

    def read_monthly_cu_file(self, file_name):
        """Read in the downloaded Credit Union file line-by-line, and insert transactions in a dictionary
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Credit Union download file
        :rtype: dict
        """
        '''
        The old format of the Credit Union output files of the C# budget program was the same as the
        download files and included many fields that are not used in budget calculations. This wasted
        time and space. More troublesome was that the output files did not include the calculated budget
        category.  This meant that the budget had to be looked up for almost EVERY RECORD in EVERY FILE,
        EVERY TIME the files were read in.  This was a HUGE performance hit. The new files (for backup
        purposes) will have a different format: only the fields that are used will be saved, including
        the budget category. The only time the budget category will have to be looked up is when the
        download file is first processed to be added to the DATABASE.
        '''
        first_line = '"Transaction ID","Posting Date","Effective Date","Transaction Type","Amount",' \
                     '"Check Number","Reference Number","Description","Transaction Category","Type",' \
                     '"Balance"'

        later_first_line_1 = '"Transaction ID","Posting Date","Effective Date","Transaction Type",' \
                             '"Amount","Check Number","Reference Number","Payee","Memo",' \
                             '"Transaction Category","Type","Balance"'

        later_first_line_0 = '"Transaction_Date","Transaction_ID","TranDesc","ExtDesc","Description",' \
                             '"Fee","Amount","Other_Charges","Balance","Post_Date","Check_Number"'

        early_first_line = '"Transaction_Date","Transaction_ID","Description","Fee","Amount",' \
                           '"Other_Charges","Balance","Post_Date","Check_Number"'

        # There are many differences in the file format for CU after 1/25/2016.
        # All fields are book-ended by double-quotes
        #    Transaction ID: is a space-delimited field consisting of:
        #        Posting date (YYYYMMDD)
        #        454292 just those 6 digits, don't know what they are or if they will change in the
        #          future.
        #        Amount in pennies (absolute value, with commas every third digit)
        #        4 groups of three digits comma-delimited, eg, 201,601,088,564
        #            The 12 digits when concatenated are taken to be the Post
        #            Date as YYYYMMDD and old-format Transaction_ID minus the leading 'ID'.
        #            For example, 201,601,088,564 from above are combined together: 201601088564 and are
        #              interpreted as YYYYMMDDIIII, or '1/8/2016', 'ID8564'
        #    Posting Date: as M/D/YYYY
        #    Effective Date: as M/D/YYYY
        #    Transaction Type: as Debit, Credit, Check
        #    Amount: as [-]d+\.ddddd
        #    Check Number: (empty if Transaction Type is not Check)
        #    Reference Number: 9-digit, appears to be a unique number which decrements by one for every
        #      new transaction
        #    Description: Details of who
        #    Transaction Category: Mostly empty, but sometimes has a budget category (bank-assigned)
        #    Type: Debit Card, ACH, Withdrawal, Transfer, sometimes empty
        #    Balance: Amount remaining in checking account
        # The difference between the monthly file formats for CU between Mar2006 and Apr2006, is the
        #   later dates added two fields
        #      "TranDesc" and "ExtDesc"
        # The later records split the old Description field into TranDesc and ExtDesc, leaving the
        #   Description field the same as before
        line_num = 0
        expected_fields = 11
        output_dict = {}
        index_transaction_date = 1
        index_transaction_id = 6
        index_transaction_amount = 4
        index_transaction_check_num = 5
        index_payee = 7
        with open(file_name) as file_ptr:
            for line in file_ptr:
                desc = ''
                bud_cat = ''
                line = line.rstrip().lstrip()
                if not line:
                    continue  # ignore blank lines
                #
                # First line stuff
                #
                if line_num == 0:
                    if line == first_line:
                        line_num += 1
                    else:
                        self.logger.log('###############################################')
                        self.logger.log('###############################################')
                        self.logger.log('###############################################')
                        self.logger.log('')
                        self.logger.log('{} has unexpected header.'.format(file_name))
                        self.logger.log('expected/got\n{}\n{}'.format(first_line, line))
                        self.logger.log('')
                        self.logger.log('###############################################')
                        self.logger.log('###############################################')
                        self.logger.log('###############################################')

                        self.unexpected_header.append(path.basename(file_name))
                        return dict()
                #
                # Process all other lines
                #
                else:
                    # Clear any commas inside quoted fields
                    line = transferUtils.clear_commas_in_quotes(' ', line)

                    # Look for in-line comments, strip them from the line, but keep them for later
                    comment = ''
                    idx = line.find('//')
                    if idx >= 0:
                        comment = line[idx:]
                        line = line[:idx]

                    # remove all double-quote characters (by this point it is guaranteed that there are
                    # no extraneous commas)
                    line = line.translate(None, '"')

                    # split the line into comma-separated fields
                    fields = line.split(',')

                    # verify there are no FEWER than the expected number of fields (can be greater)
                    if len(fields) < expected_fields:
                        self.logger.log('Missing fields in file {}. Expected at least {} but got {}. '
                                        'Line:\n{}'.format(file_name, expected_fields, len(fields),
                                                           line))
                        sys.exit(1)

                    if fields[expected_fields:]:
                        comment = str(fields[expected_fields:]) + comment

                    # parse the first field -- transaction date (split off time part)
                    trans_date = fields[index_transaction_date].split(' ')[0]  # default value

                    # Transaction ID
                    tid = fields[index_transaction_id]

                    # If the record is a check, use the checks DATABASE to fill in the budget fields
                    # For UNRECORDED checks, we will need to fill in budget fields with default values
                    check_num = ''
                    transaction_payee = fields[index_payee]
                    budget_category_dict = dict()
                    if fields[index_transaction_check_num]:  # a check
                        # value of index_transaction_check_num depends on old or new format
                        check_num = fields[index_transaction_check_num]

                        # There is a check in the CU DATABASE with number '1'.
                        # We're renumbering it for the DATABASE
                        if check_num == '1':
                            check_num = '999999'

                        # The check info resides in the checks table. The 'main' entry for the check has
                        # no useful budget information.
                        desc = 'Check'
                        budget_category_dict[0] = ['XXX', 0, '']

                    # If the record is not a check, fill in the budget info from the payee DATABASE or
                    # optional extra budget fields
                    else:
                        # Lookup the default budget category from the payee DATABASE
                        # defaults to 'UNKNOWN'
                        bud_cat = self.lookup_payee_category(transaction_payee, trans_date)

                        # set the default budget date and amount from the transaction date and amount
                        bud_amt = fields[index_transaction_amount]

                        # process the extra budget fields which may mean extra DATABASE records
                        budget_category_dict = transferUtils.process_budget_fields(
                            fields[expected_fields:], bud_amt, bud_cat, trans_date, tid)

                    transferUtils.insert_entry_into_dict(
                        budget_category_dict,
                        tid,
                        trans_date,
                        desc if check_num else ' '.join(transaction_payee.split()) if transaction_payee
                        else fields[index_payee],
                        check_num,
                        'b',
                        fields[index_transaction_amount],
                        comment,
                        output_dict)
                    line_num += 1
                    # end if line_num == 0
                    # end for each line
        # end with open

        self.logger.log('readMonthlyCUFile processed {} records from {}\n'.format(line_num, file_name))
        return output_dict

