import hashlib
import json
import transferUtils
import header as h
from datetime import datetime
from utils import Logger
import transferFilesToDB


def convert_downloads_file(download_file, map_file, format_file, key, transfer, logger):
    """Read in the downloads file line-by-line, and insert transactions in a dictionary
    Return the dictionary with the downloaded transactions.

    :param str download_file: name of the download file
    :param str map_file: name of the map file
    :param str format_file: name of the format file
    :param str key: identifying key in map file. Currently 'cu', 'citi', 'discover'
    :param transferFilesToDB.TransferMonthlyFilesToDB transfer: required object method
    :param Logger logger: logging method
    :rtype: dict
    """
    with open("supported_downloads.json", "r") as f:
        supported = json.load(f)
    assert key in supported, f"Key '{key}' not found in supported_downloads '{supported}'"
    with open(map_file, "r") as f:
        field_maps = json.load(f)
    assert key in field_maps, f"Key '{key}' not found in map file {map_file}"
    field_map = field_maps[key]
    header = h.Header(json_file=format_file)
    transaction_type = field_map['type']

    line_num = 0
    expected_fields = header.num_fields
    output_dict = {}
    index_transaction_date = field_map['date']
    if 'tid' in field_map:
        index_transaction_id = field_map['tid']
    else:
        index_transaction_id = None
    if 'check' in field_map:
        index_transaction_check_num = field_map['check']
    else:
        index_transaction_check_num = None
    if 'status' in field_map:
        index_status = field_map['status']
    else:
        index_status = None
    if 'credit' in field_map and 'debit' in field_map:
        index_transaction_amount = None
        index_transaction_credit = field_map['credit']
        index_transaction_debit = field_map['debit']
    else:
        index_transaction_amount = field_map['amount']
        index_transaction_credit = None
        index_transaction_debit = None
    index_payee = field_map['payee']

    with open(download_file, "r") as file_ptr:
        for line in file_ptr:
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
            # Validate first line/header
            #
            if line_num == 0:
                try:
                    header.validate_header_field_names(fields)
                except AttributeError:
                    logger.log('###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################\n')
                    logger.log(f'{transaction_type.upper()} download file has unexpected header.')
                    logger.log(f'Run "python3 new_header.py {transaction_type}" to create new header')
                    logger.log('\n###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################')
                    raise
                line_num += 1
                continue
            #
            # Process all other lines
            #
            header.validate_data_field_values(fields)

            # some download files have a "status" field which indicates if transaction is pending or cleared
            # skip "pending" transactions
            if index_status and fields[index_status].lower() == 'pending':
                line_num += 1
                continue

            # transaction date
            transaction_date = fields[index_transaction_date]

            # payee
            transaction_payee = fields[index_payee]

            # amount
            # some download files split the transaction amount into a "credit" field or a "debit" field
            if index_transaction_amount is not None:
                tamt = float(fields[index_transaction_amount])
            else:
                tamt = float(fields[index_transaction_credit] if fields[index_transaction_credit] else
                             fields[index_transaction_debit])
            if field_map['negate']:
                tamt *= -1.0
            transaction_amount = f"{tamt:.2f}"

            # transaction ID
            # Some financial institutions include a unique ID field for each transaction in their download.
            # If there is one for this download, use it. Otherwise create a unique ID by combining the specified
            # fields together from the field_map, and optionally converting it to an md5 checksum.
            if index_transaction_id is not None:
                transaction_id = fields[index_transaction_id]
            else:
                tid = ""
                for fld in field_map['tid_fields']:
                    if fld == "date" and 'tid_date_format' not in field_map:
                        tid += transaction_date
                    elif fld == "amount":
                        tid += transaction_amount
                    elif fld == "payee":
                        tid += transaction_payee
                    else:  # use whatever field specified - unique to each field map
                        assert fld in field_map, f"Key field '{fld}' not found in field_map for {key}"
                        # Some downloads have more than one date, such as Discover card which has "Trans. Date", and
                        # "Post Date" and use all the dates in their transaction ID. Right now we assume the original
                        # date formats are always "mm/dd/yyyy". Future enhancement will allow specification of
                        # original date formats. Right now there are only 2 supported reformatted date formats.
                        if fld.startswith('date') and 'tid_date_format' in field_map:
                            assert field_map['tid_date_format'] in ["yyyymmdd", "mmddyyyy"], (
                                f"tid_date_format {field_map['tid_date_format']} must be one of 'yyyymmdd' or "
                                f"'mmddyyyy'")
                            date_arr = fields[field_map[fld]].split('/')
                            if field_map['tid_date_format'] == 'yyyymmdd':
                                tid += f"{date_arr[2]}{date_arr[0]}{date_arr[1]}"
                            elif field_map['tid_date_format'] == 'mmddyyyy':
                                tid += f"{date_arr[0]}{date_arr[1]}{date_arr[2]}"
                        else:
                            tid += fields[field_map[fld]]
                if field_map['md5']:
                    transaction_id = hashlib.md5(tid.encode('utf-8')).hexdigest()
                else:
                    transaction_id = tid
            transaction_id = transaction_id.replace(' ', '')  # remove all spaces

            check_num = ''
            desc = ''
            if index_transaction_check_num is not None and fields[index_transaction_check_num]:
                # If the record is a check, use the checks DATABASE to fill in the budget fields
                # For UNRECORDED checks, we will need to fill in budget fields with default values
                budget_category_dict = dict()
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
                bud_cat = transfer.lookup_payee_category(transaction_payee, transaction_date)

                # set the default budget date and amount from the transaction date and amount
                bud_amt = transaction_amount

                # process the extra budget fields which may mean extra DATABASE records
                budget_category_dict = transferUtils.process_budget_fields(
                    fields[expected_fields:], bud_amt, bud_cat, transaction_date, transaction_id)

            transferUtils.insert_entry_into_dict(
                budget_category_dict,
                transaction_id,
                transaction_date,
                desc if check_num else ' '.join(transaction_payee.split()) if transaction_payee
                else fields[index_payee],
                check_num,
                transaction_type,
                transaction_amount,
                comment,
                output_dict)
            line_num += 1
        # end for each line
    # end with open

    logger.log(f"convert_downloads_file processed {line_num} records from {download_file}\n")
    return output_dict
