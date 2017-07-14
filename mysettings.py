"""Holds static classes"""


class g(object):
    """Field indices for main and checks tables queries. Same order for data arrays."""
    tDate = 0         # transaction date
    tID = 1           # transaction ID
    tPayee = 2        # transaction payee/description
    tCkn = 3          # transaction check number (if a check)
    tType = 4         # transaction type (cleared date for checks query)
    tAmount = 5       # transaction amount
    tBudarr = 6       # transaction budget array (list of lists)
    tComment = 7      # transaction comment, if any
    tClearDate = 8    # check clear date (checks only)
    tClearDateQ = 4   # check clear date (checks only) from query
    tCommentQ = 9     # transaction comment field# from query
