import sys
import re
import transferUtils


class Mixin(object):
    def read_download_barclay_file(self, file_name):
        """Read in the downloaded Barclay Card file line-by-line, and insert transactions in a
        dictionary. OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Barclay Card download file
        :rtype: dict
        """
        # This is the download file format:
        #
        # ...<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20150203050000.000<DTUSER>20150203050000.000<TRNAMT>566.64<FITID>75140215034020315130448108<NAME>PAYMENT RECV'D CHECKFREE</STMTTRN>...
        #
        line_num = 0
        output_dict = dict()
        with open(file_name) as file_ptr:
            for line in file_ptr:
                if '<STMTTRN>' in line:
                    transactions = line.split('<STMTTRN>')
                    # for each transaction (element 0 does not contain what we are looking for)
                    for trans in transactions[1:]:
                        if not '<DTPOSTED>' in trans or \
                                not '<TRNAMT>' in trans or \
                                not '<FITID>' in trans or \
                                not '<NAME>' in trans:
                            self.logger.log(f"Missing fields in file {file_name}. Expected 4 fields, but one or "
                                            f"more are missing: {trans}")
                            sys.exit(1)
                        match_obj = re.search(r'<FITID>([^<]+)<', trans)
                        if match_obj:
                            trans_ref = match_obj.group(1)
                        else:
                            self.logger.log('Error matching <FITID> in transaction "{}" in file {}'.
                                            format(trans, file_name))
                            sys.exit(1)
                        match_obj = re.search(r'<DTPOSTED>([^<]+)<', trans)
                        if match_obj:
                            trans_date = (match_obj.group(1)[4:6]
                                          + '/' +
                                          match_obj.group(1)[6:8]
                                          + '/' +
                                          match_obj.group(1)[:4])
                        else:
                            self.logger.log('Error matching <DTPOSTED> in transaction "{}" in file {}'.
                                            format(trans, file_name))
                            sys.exit(1)
                        match_obj = re.search(r'<TRNAMT>([^<]+)<', trans)
                        if match_obj:
                            trans_amt = match_obj.group(1)
                        else:
                            self.logger.log('Error matching <TRNAMT> in transaction "{}" in file {}'.
                                            format(trans, file_name))
                            sys.exit(1)
                        match_obj = re.search(r'<NAME>([^<]+)<', trans)
                        if match_obj:
                            trans_payee = match_obj.group(1)
                        else:
                            self.logger.log('Error matching <NAME> in transaction "{}" in file {}'.
                                            format(trans, file_name))
                            sys.exit(1)

                        # lookup the default budget category from the payee DATABASE
                        # defaults to 'UNKNOWN'
                        bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                        # set the default budget date and amount from the transaction date and amount
                        bud_date = trans_date
                        bud_amt = trans_amt

                        # insert the record(s) into the dictionary
                        budget_category_dict = dict()
                        budget_category_dict[0] = [bud_cat, bud_amt, bud_date]
                        transferUtils.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date,
                                                             trans_payee, '', 'y', trans_amt, '',
                                                             output_dict)
                        line_num += 1
                        # end for each transaction
                        # end if <STMTTRN> found in line
                        # end for each line in file
        self.logger.log('read_download_barclay_file processed {} records from {}\n'.
                        format(line_num, file_name))
        return output_dict

    def read_monthly_barclay_file(self, file_name):
        """Read in the downloaded Barclay Card file line-by-line, and insert transactions in a
        dictionary. OBSOLETE
        Return the dictionary with the downloaded transactions.

        :param str file_name: name of the Barclay Card download file
        :rtype: dict
        """
        # This is the monthly file format:
        #   0  1  2             3                      4         5
        # 2011,04,04,252478010910000016899273001,BOMBAY MASALA,31.00
        # tyr tmo tday         tref                  payee      tamt
        line_num = 0
        expected_fields = 6
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

                # remove all double-quote characters (by this point it is guaranteed that there are no
                # extraneous commas)
                line = line.replace('"', '')

                # split the line into fields (comma-separated)
                field = line.split(',')

                # verify there are no FEWER than the expected number of fields (can be greater)
                if len(field) < expected_fields:
                    self.logger.log(f"Missing fields in file {file_name}. Expected at least {expected_fields} but "
                                    f"got {len(field)}. Line:\n{line}")
                    sys.exit(1)

                # parse the date field -- transaction date
                trans_date = field[1]+'/'+field[2]+'/'+field[0]

                # parse the transaction reference
                trans_ref = field[3]

                # transaction amount
                # all transaction amounts shown as a positive number
                trans_amt = field[5]

                # transaction payee
                # strip out extra spaces
                trans_payee = ' '.join(field[4].split())

                # lookup the default budget category from the payee DATABASE
                # defaults to 'UNKNOWN'
                bud_cat = self.lookup_payee_category(trans_payee, trans_date)

                # process the extra budget fields which may mean extra DATABASE records
                budget_category_dict = transferUtils.process_budget_fields(field[expected_fields:],
                                                                           trans_amt, bud_cat,
                                                                           trans_date, trans_ref)

                # insert the record(s) into the dictionary
                transferUtils.insert_entry_into_dict(budget_category_dict, trans_ref, trans_date,
                                                     trans_payee, '', 'y', trans_amt, comment,
                                                     output_dict)
                line_num += 1
                # end for
        self.logger.log('read_monthly_barclay_file processed {} records from {}\n'.
                        format(line_num, file_name))
        return output_dict

