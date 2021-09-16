import sys
import json
import transferUtils
import header as h
from utils import Logger
import transferFilesToDB


def read_monthly_discover_file(file_name, transfer, logger):
    """Read in the downloaded Discover Card file line-by-line, and insert transactions in a
    dictionary.
    Return the dictionary with the downloaded transactions.

    :param str file_name: name of the Discover Card download file
    :param transferFilesToDB.TransferMonthlyFilesToDB transfer: required object method
    :param Logger logger: logging method
    :rtype: dict
    """

    # Discover card does not have a unique identifier for each transaction. We
    # have to create one, but it is not fool-proof: combine the 2 dates, payee, amount, and payee type
    # with all the spaces removed. Most of the time the resulting string is unique. But once in a
    # while two or more transactions occur on the same day to the same payee for the same amount and
    # then they have to be distinguished. This is problematic.

    header = h.Header(json_file="discover_download_format.json")
    with open("map_download_to_db.json", "r") as f:
        field_map = json.load(f)['discover']

    line_num = 0
    expected_fields = header.num_fields
    check_dict = {}
    output_dict = {}
    trans_type = field_map['type']

    with open(file_name, "r") as file_ptr:
        for line in file_ptr:
            line = line.strip()

            # ignore blank lines
            if not line:
                continue

            # Clear any commas inside quoted fields and strip any " characters
            line = transferUtils.clear_commas_in_quotes(' ', line)

            # Look for in-line comments and keep them
            comment = ''
            idx = line.find('//')
            if idx >= 0:
                comment = line[idx+2:]
                line = line[:idx]

            fields = line.split(',')

            # first line is header line
            if line_num == 0:
                # This is the file when there are no transactions in the given period
                if line.startswith('There are no statements'):
                    return output_dict

                try:
                    header.validate_header_field_names(fields)
                except AssertionError:
                    logger.log('###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################\n')
                    logger.log('Discover download file has unexpected header.')
                    logger.log('Run "python3 new_header.py discover" to create new header')
                    logger.log('\n###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################')
                    raise

                line_num += 1
                continue

            # validate remaining lines against regex templates
            header.validate_data_field_values(fields)

            # parse the first field -- transaction date
            trans_date = fields[field_map['date1']]

            # parse the transaction amount
            # Discover reverses the sign of the amounts: no sign (positive)
            # for debits, - for credits -- we reverse it to preserve
            # consistency across accounts
            trans_amt_float = float(fields[field_map['amount']])
            trans_amt_string = '%.2f' % -trans_amt_float

            # parse the transaction reference
            # some work here to get the dates in the right order and format
            date1 = fields[field_map['date1']].split('/')
            date2 = fields[field_map['date2']].split('/')
            trans_ref = ''.join([''.join([date1[2],
                                          date1[0],
                                          date1[1]]),
                                 ''.join([date2[2],
                                          date2[0],
                                          date2[1]]),
                                 fields[2].replace(' ', ''),
                                 trans_amt_string,
                                 fields[4].replace(' ', '')])

            # check_dict is here to make sure the record reference is unique
            while trans_ref in check_dict:
                logger.log(f"Discover transaction reference '{trans_ref}' is not unique. Appending 'x' to it")
                # If it's already being used, add a character to it
                trans_ref = trans_ref + 'x'

            # now the reference is unique and can be inserted into the DATABASE
            check_dict[trans_ref] = 0

            # transaction payee
            trans_payee = fields[field_map['payee']]

            # Lookup the default budget category from the payee DATABASE
            # defaults to 'UNKNOWN'
            bud_cat = transfer.lookup_payee_category(trans_payee, trans_date)
            logger.log(f"Discover transaction {trans_payee} matches to category {bud_cat}\n")

            # process the extra budget fields which may mean extra DATABASE records
            budget_category_dict = transferUtils.process_budget_fields(
                fields[expected_fields:], trans_amt_string, bud_cat, trans_date, trans_ref)

            # insert the record(s) into the dictionary
            transferUtils.insert_entry_into_dict(
                budget_category_dict, trans_ref, trans_date, trans_payee, '', trans_type, trans_amt_string, comment,
                output_dict)
            line_num += 1
        # end for line in
    # end with open(...
    logger.log(f"read_monthly_discover_file processed {line_num - 1} records from {file_name}\n")

    return output_dict
