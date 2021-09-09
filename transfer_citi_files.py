import datetime
import json
import hashlib
import transferUtils
import transferFilesToDB
import header as h
from utils import Logger


def read_monthly_citi_file(file_name, transfer, logger):
    """Read in the downloaded Citibank file line-by-line, and insert transactions in a dictionary.
    Return the dictionary with the downloaded transactions.

    :param str file_name: name of the Citibank download file
    :param transferFilesToDB.TransferMonthlyFilesToDB transfer: object with a good method
    :param Logger logger: The logging object
    :rtype: dict
    """
    '''
    Citi Card took over all Costco American Express card accounts on June 3, 2016. Citi has all
    historical Costco AMEX card transactions back to May 2014, if needed.  But those Amex-era
    download formats will be in the earlier Citi download format, not the former Amex format.

    On or before 06/02/2016:
        0                     1                   2                                                       3               4             5
    "Status",               "Date",         "Description",                                              "Debit",       "Credit",   "Member Name"
    "Cleared",           "06/02/2016",       "E 470 EXPRESS TOLLS                     ",               "32.55",           "",      "CHRIS ANDERSON"

    On or after 06/03/2016 ('format_v2'):
        0                     1                   2                                                       3               4             5
    "Status",               "Date",         "Description",                                              "Debit",       "Credit",   "Member Name"
    "Cleared",           "06/03/2016",       "AMAZON.COM                           XXXX-XXXX-XXXX-3003","8.65",           "",      "KATHY ANDERSON"

        0                     1                   2                                                        3               4
    "Status",               "Date",         "Description",                                              "Debit",       "Credit"
    "Cleared",           "11/30/2016",      "KING SOOPERS #0729 FUEL  ERIE         CO",                    "",          "22.88"

    On or after 01/10/2019:
        0                1                    2                                                       3            4          5
    Status,            Date,             Description,                                               Debit,       Credit,  Member Name
    Cleared,           06/03/2016,       "AMAZON.COM                           XXXX-XXXX-XXXX-3003",8.65,           ,     KATHY ANDERSON


    The only difference between the two formats is very small: The earlier format does not have the
    crypto-card number at the end of the description fields.
    Both Debit and Credit values are positive.
    
    The 3rd format is the same as the previous format, except all double-quotes are removed except
    around the Description field. There are also no

    TODO: Talk to Citi about adding transaction reference fields to download file
    DONE: Talked to Citi about adding transaction ID fields. They have passed the request on to their
    tech guys.
    '''

    header = h.Header(json_file="citi_download_format.json")
    with open("map_download_to_db.json", "r") as f:
        field_map = json.load(f)['citi']

    line_num = 0
    expected_fields = header.num_fields
    output_dict = {}
    format_v2 = False
    format_v3 = False

    with open(file_name, "r") as file_ptr:
        line_num = 0
        line = file_ptr.readline()
        while line:
            # Older versions of citi download files would sometimes split each line in two. So
            # we had to join them back together.
            #
            # Check for normal end-of-line characters. If not, read the next line and join together.
            # if ord(line[-2]) != 13 and ord(line[-1]) == 10:
            #     print('Jacked line: "{}" {}-{}'.format(line, ord(line[-2]), ord(line[-1])))
            #     line2 = file_ptr.readline()  # read in the next line
            #     line = line[:-1] + line2  # strip off last char of first line and join to 2nd line
            #     print('\nJoined: {}'.format(line.strip()))
            # else:
            #     print('\nNormal: {}'.format(line.strip()))
            logger.log(f"Normal: {line.strip()}")

            # strip all leading and trailing spaces and new-lines
            line = line.strip()

            # ignore blank lines
            if not line:
                line = file_ptr.readline()
                continue

            # Clear any commas inside quoted fields and strip remaining " characters
            line = transferUtils.clear_commas_in_quotes('', line)

            # Look for in-line comments and keep them
            comment = ''
            idx = line.find('//')
            if idx >= 0:
                comment = line[idx+2:]
                line = line[:idx]

            # split the line into fields (comma-separated)
            fields = line.split(',')

            # Validate the header field names
            if line_num == 0:
                try:
                    header.validate_header_field_names(fields)
                except AssertionError:
                    logger.log('###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################\n')
                    logger.log('Citi download file has unexpected header.')
                    logger.log('Run "python3 new_header.py citi" to create new header')
                    logger.log('\n###############################################')
                    logger.log('###############################################')
                    logger.log('###############################################')
                    raise

                line = file_ptr.readline()
                line_num += 1
                continue

            # Skip if it's a pending transaction. Sometimes transaction details change when they
            # transition from Pending to Cleared and a slightly different form of the exact same
            # transaction is created and inserted into the DATABASE the next time the Citi
            # transaction file is downloaded and processed by this script, creating a double entry.
            # To prevent this, only consider Cleared transactions which by assumption do not change
            # over time.
            if 'pending' in fields[field_map['status']].lower():
                line = file_ptr.readline()
                line_num += 1
                continue

            # Validate the data values
            header.validate_data_field_values(fields)

            # parse the second fields -- transaction date
            trans_date = fields[field_map['date']]  # mm/dd/yyyy

            # don't parse or insert format_v3 Citi records transacted before 1/1/2019
            # This prevents double records since the payee field has changed and therefore the
            # calculated trans_ref field will be different.
            datefields = [int(n) for n in trans_date.split('/')]
            trans_date_object = datetime.date(datefields[2], datefields[0], datefields[1])
            if format_v3 and trans_date_object < datetime.date(2019, 1, 1):
                logger.log("Citi card records transacted prior to 1 Jan 2019 are not processed")
                line = file_ptr.readline()
                line_num += 1
                continue

            # transaction amount (fields 3 and 4 are mutually exclusive:
            # one or the other has a value, not both)
            # BUT THEY BOTH MAY BE EMPTY!
            if fields[field_map['debit']]:  # debit value (no sign)
                trans_amt = '-'+fields[field_map['debit']]  # Debits need to be negative value
            elif fields[field_map['credit']]:  # credit value (has a negative sign)
                trans_amt = fields[field_map['credit']].replace('-', '')  # strip off negative sign
            else:
                trans_amt = '0.00'

            # transaction payee
            # format_v2: strip off optional credit card number at end of fields (cut len to 37)
            # format_v3: reconstruct format_v2 payee format:
            #            25 char right-padded,13 char right-padded,2 char
            trans_payee = fields[field_map['payee']]

            # strip-off optional credit card number at end of fields for format_v2 only
            if format_v2:
                # strip off crypto-card-number
                trans_payee = trans_payee[0:37]

            # strip off any and all trailing white-space
            trans_payee = trans_payee.strip()

            # Lookup the default budget category from the payee DATABASE defaults to 'UNKNOWN'
            bud_cat = transfer.lookup_payee_category(trans_payee, trans_date)

            # TEMP: create a transaction reference from the value of each fields. Empty fields get a
            # value
            hash_key = trans_date+trans_amt+trans_payee+fields[field_map['member']]
            trans_ref = hashlib.md5(hash_key.encode('utf-8')).hexdigest()
            logger.log(f"{hash_key} => {trans_ref}")

            logger.log(f"Citi transaction {trans_payee} matches to category {bud_cat}\n")

            # process the extra budget fields which may mean extra DATABASE records
            budget_category_dict = transferUtils.process_budget_fields(
                fields[expected_fields:], trans_amt, bud_cat, trans_date, trans_ref)

            # insert the record(s) into the dictionary
            transferUtils.insert_entry_into_dict(
                budget_category_dict, trans_ref, trans_date, trans_payee, '', 'C', trans_amt, comment, output_dict)
            line_num += 1
            line = file_ptr.readline()
        # end while
    # end with open(...

    logger.log(f"read_monthly_citi_file processed {line_num} records from {file_name}\n")
    return output_dict

