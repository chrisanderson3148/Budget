import json
import transferUtils
import header as h
from datetime import datetime
from utils import Logger
import transferFilesToDB


def read_monthly_cu_file(file_name, transfer, logger):
    """Read in the downloaded Credit Union file line-by-line, and insert transactions in a dictionary
    Return the dictionary with the downloaded transactions.

    :param str file_name: name of the Credit Union download file
    :param transferFilesToDB.TransferMonthlyFilesToDB transfer: required object method
    :param Logger logger: logging method
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
                 '"Balance","Memo","Extended Description"'

    later_first_line_2 = '"Transaction ID","Posting Date","Effective Date","Transaction Type",' \
                         '"Amount","Check Number","Reference Number","Description",' \
                         '"Transaction Category","Type","Balance"'

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
    with open("map_download_to_db.json", "r") as f:
        field_map = json.load(f)['cu']
    header = h.Header(json_file='cu_download_format.json')
    trans_type = field_map['type']

    line_num = 0
    expected_fields = header.num_fields
    output_dict = {}
    index_transaction_date = field_map['date']
    index_transaction_id = field_map['tid']
    index_transaction_amount = field_map['amount']
    index_transaction_check_num = field_map['check']
    index_payee = field_map['payee']
    index_reference_id = field_map['reference']

    with open(file_name, "r") as file_ptr:
        for line in file_ptr:
            desc = ''
            bud_cat = ''
            line = line.strip()
            if not line:
                continue  # ignore blank lines

            # Clear any commas inside quoted fields, and strip all " chars from line
            line = transferUtils.clear_commas_in_quotes(' ', line)

            # Look for in-line comments, strip them from the line, but keep them for later
            comment = ''
            idx = line.find('//')
            if idx >= 0:
                comment = line[idx:]
                line = line[:idx]

            # split the line into comma-separated fields
            fields = line.split(',')

            #
            # First line stuff
            #
            if line_num == 0:
                try:
                    header.validate_header_field_names(fields)
                    line_num += 1
                except AttributeError:
                    logger.log('###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################\n')
                    logger.log('CU download file has unexpected header.')
                    logger.log('Run "python3 new_header.py cu" to create new header')
                    logger.log('\n###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################')
                    raise
                continue
            #
            # Process all other lines
            #
            header.validate_data_field_values(fields)

            # Instead, ignore any extra fields
            if len(fields) > expected_fields:
                fields = fields[:expected_fields]

            # parse the first field -- transaction date (split off time part)
            trans_date = fields[index_transaction_date].split(' ')[0]  # default value

            # Transaction ID
            # The "Reference Number" field in the download file is not reliable - sometimes it gets changed for
            # records already inserted into the database which messes things up. Starting 9/1/2021 we will start
            # using "Transaction ID" field (stripped of commas and spaces) as the transaction ID. There appears to
            # be a serial number embedded in that field (last 5 digits).
            trans_datetime = datetime.strptime(trans_date, "%m/%d/%Y")
            sept_2021 = datetime.strptime("9/1/2021", "%m/%d/%Y")
            if trans_datetime >= sept_2021:
                tid = fields[index_transaction_id].replace(' ', '')
            else:
                tid = fields[index_reference_id]

            # If the record is a check, use the checks DATABASE to fill in the budget fields
            # For UNRECORDED checks, we will need to fill in budget fields with default values
            check_num = ''
            transaction_payee = fields[index_payee]

            tamt = float(fields[index_transaction_amount])
            if field_map['negate']:
                tamt *= -1.0
            transaction_amount = f"{tamt:.2f}"

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
                bud_cat = transfer.lookup_payee_category(transaction_payee, trans_date)

                # set the default budget date and amount from the transaction date and amount
                bud_amt = transaction_amount

                # process the extra budget fields which may mean extra DATABASE records
                budget_category_dict = transferUtils.process_budget_fields(
                    fields[expected_fields:], bud_amt, bud_cat, trans_date, tid)

            transferUtils.insert_entry_into_dict(
                budget_category_dict,
                tid,
                trans_date,
                desc if check_num else transaction_payee,
                check_num,
                trans_type,
                transaction_amount,
                comment,
                output_dict)
            line_num += 1
        # end for each line
    # end with open

    logger.log(f"readMonthlyCUFile processed {line_num} records from {file_name}\n")
    return output_dict

