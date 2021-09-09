import header as h
import transferUtils


cu_header = h.Header(json_file="cu_download_format.json")
with open("downloads/ExportedTransactions.csv", "r") as f:
    line_num = 0
    for line in f:
        line = line.strip()
        line = transferUtils.clear_commas_in_quotes(' ', line)
        if line_num == 0:
            cu_header.validate_header_field_names(line.split(','))
        else:
            cu_header.validate_data_field_values(line.split(','))
        line_num += 1

citi_header = h.Header(json_file="citi_download_format.json")
with open("downloads/Citi-RecentActivity.CSV", "r") as f:
    line_num = 0
    for line in f:
        line = line.strip()
        line = transferUtils.clear_commas_in_quotes(' ', line)
        if line_num == 0:
            citi_header.validate_header_field_names(line.split(','))
        else:
            citi_header.validate_data_field_values(line.split(','))
        line_num += 1

discover_header = h.Header(json_file="discover_download_format.json")
with open("downloads/Discover-RecentActivity.csv", "r") as f:
    line_num = 0
    for line in f:
        line = line.strip()
        line = transferUtils.clear_commas_in_quotes(' ', line)
        if line_num == 0:
            discover_header.validate_header_field_names(line.split(','))
        else:
            discover_header.validate_data_field_values(line.split(','))
        line_num += 1
