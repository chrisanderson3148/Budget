"""Static helper methods"""

import sys
import collections


def clear_commas_in_quotes(replace_char, line):
    """Replaces all commas ',' inside double-quotes with the given replacement character.
    Returns the same line with all the bad commas replaced.

    :param str replace_char: the character to replace the bad comma
    :param str line: the line containing the potentially bad comma(s)
    :rtype: str
    """
    start = 0
    while line.find('"', start) != -1:
        idx1 = line.find('"', start)  # index of opening quote
        if idx1 == -1:
            break
        idx2 = line.find('"', idx1+1)  # index of closing quote
        if idx2 == -1:  # Didn't find a closing quote? Barf
            print(f"Improperly formed line: opening \" but no closing \" in line\n{line}")
            sys.exit(1)

        # replace all found commas with replace_char within the opening and closing quotes
        while True:
            comma_index = line.find(',', idx1, idx2)
            if comma_index >= 0:  # replace found comma with replacement char
                line = line[:comma_index] + replace_char + line[comma_index + 1:]
            else:  # found all commas (or there were none)
                break

        # move after closing quote to begin another search for an opening quote
        start = idx2 + 1
    # now line is clear of confusing commas
    line = line.replace('"', '')  # remove all double-quotes
    return line


def process_budget_fields(extra_field, transaction_amount, default_category, transaction_date, transaction_reference):
    """Process the budget fields in the payee file (???)
    Returns a dictionary of the payee file

    Each field in extra_field can be like: 'BUDCAT[=BUDAMT[=BUDDATE]]', or 'DATE=<BUDDATE>'

    :param list[str] extra_field:
    :param str transaction_amount:
    :param str default_category:
    :param str transaction_date:
    :param str transaction_reference:
    :rtype: dict
    """
    budget_category = ''
    budget_amount = ''
    budget_date = ''
    idx = 0
    budget_dict = {}
    for field in extra_field:
        subfield = field.split('=')
        if subfield[0] == 'DATE':
            if budget_date:
                budget_dict[idx] = [budget_category, budget_amount, budget_date]
                budget_category = ''
                budget_amount = ''
                budget_date = ''
                idx += 1
            else:
                budget_date = subfield[1]
        else:
            if budget_category:
                budget_dict[idx] = [budget_category, budget_amount, budget_date]
                budget_category = ''
                budget_amount = ''
                budget_date = ''
                idx += 1
            if len(subfield) == 1:
                budget_category = subfield[0]
            elif len(subfield) == 2:
                budget_category = subfield[0]
                budget_amount = subfield[1]
            else:
                budget_category = subfield[0]
                budget_amount = subfield[1]
                budget_date = subfield[2]

    # assign the last or only row
    budget_dict[idx] = [budget_category, budget_amount, budget_date]

    # finish processing missing budget info with (calculated) defaults
    tran_amt_isneg = float(transaction_amount) < 0.0

    # remainder is a double and is always POSITIVE
    remainder = abs(float(transaction_amount))

    # for key, val in collections.OrderedDict(sorted(budget_dict.items())).iteritems():
    for key in budget_dict:
        if not budget_dict[key][0]:
            budget_dict[key][0] = default_category  # default

        # The assumption is that all budget amounts are positive, but use
        # the same sign as the transaction amount
        if not budget_dict[key][1]:  # no budget amount?
            # assign any remainder to it
            budget_dict[key][1] = '%.2f' % (-1.0*remainder if tran_amt_isneg else remainder)
            remainder = 0.0
        else:  # otherwise decrement remainder by the budget amount
            # keep track of the remainder
            remainder = remainder - float(budget_dict[key][1])
            if tran_amt_isneg and not budget_dict[key][1].startswith('-'):
                budget_dict[key][1] = '-'+budget_dict[key][1]
            if remainder < 0.0:  # something didn't add up
                remainder = 0.0
                print(f"Calculating amount for {budget_dict[key]} and got a remainder less than zero (transaction_"
                      f"reference={transaction_reference}, extra fields={','.join(extra_field)})")
        # end if
        if not budget_dict[key][2]:  # no budget date?
            budget_dict[key][2] = transaction_date  # assign transaction date
    # end for
    return budget_dict


def insert_entry_into_dict(budget_dict, transaction_reference, transaction_date,
                           transaction_payee, transaction_check_num, transaction_type,
                           transaction_amount, transaction_comment, output_dict):
    """Insert the transaction (possibly multi-budget) in to the output_dict dictionary

    :param dict budget_dict:
    :param str transaction_reference:
    :param str transaction_date:
    :param str transaction_payee:
    :param str transaction_check_num:
    :param str transaction_type:
    :param str transaction_amount:
    :param str transaction_comment:
    :param dict output_dict:
    :return:
    """
    if len(budget_dict) == 1:  # there is only one line for this transaction
        bud = budget_dict[0]
        output_dict[transaction_reference] = [transaction_date, transaction_reference,
                                              transaction_payee, transaction_check_num,
                                              transaction_type, transaction_amount,
                                              bud[0], bud[1], bud[2], transaction_comment]
    else:
        for key, bud in collections.OrderedDict(sorted(budget_dict.items())).iteritems():
            my_key = transaction_reference + '-' + str(key)
            output_dict[my_key] = [transaction_date, transaction_reference, transaction_payee,
                                   transaction_check_num, transaction_type, transaction_amount,
                                   bud[0], bud[1], bud[2], transaction_comment]
