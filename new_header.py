#!/usr/bin/python3
import sys
import header as h
import json


def print_curr_vs_new_header_field_names(curr_header, new_header):
    """Just like the name says.

    :param h.Header curr_header: current header
    :param h.Header new_header: new header
    :returns bool: if there are differences or not
    """
    differences = False
    print(f"\n{'   Current field name':<25}{'   New field name':<25}\n-----------------------------------------------")
    for i in range(max(curr_header.num_fields, new_header.num_fields)):
        if i >= curr_header.num_fields:
            curr_name = "-----"
            differences = True
        else:
            curr_name = curr_header.fields[i].name
        if i >= new_header.num_fields:
            new_name = "-----"
            differences = True
        else:
            new_name = new_header.fields[i].name
        print(f"{i:2d} {curr_name:<25}{new_name:<25}{'' if curr_name == new_name else ' <----'}")
        if curr_name != new_name:
            differences = True
    print("\n")
    return differences


def copy_curr_to_new_header(curr_header, new_header, i):
    """Like the name says.

    :param h.Header curr_header: current header
    :param h.Header new_header: new header
    :param int i: index of both curr and new header field"""
    for j in range(curr_header.num_fields):
        if curr_header.fields[j].name == new_header.fields[i].name:
            new_header.fields[i].data_type = curr_header.fields[j].data_type
            new_header.fields[i].regex = curr_header.fields[j].regex
            print(f"Copied curr_header field {j} to new_header field {i}")
            break


def create_new_header_rules(new_header, i):
    """Create new rules for given new header field.

    :param h.Header new_header: new header
    :param int i: index of new header field to create rules
    """
    print(f"\nNew header field {i}: {new_header.fields[i]}")
    while True:
        ans = input("Enter data type for field (one of 'int', 'float', 'date', 'str', or 'freestr'): ")
        if ans.lower() in ["int", "float", "date", "str", "freestr"]:
            new_header.fields[i].set_data_type(ans.lower())
            break
        else:
            print(f"{ans.lower()} is not in that list. Try again.")
    print(f"New header field {i}: {new_header.fields[i]}")
    if new_header.fields[i].data_type in ["float", "int", "date", "str"]:
        ans = input("Enter regex for field: ")
        new_header.fields[i].set_regex(ans)
        print(f"New header field {i}: {new_header.fields[i]}")
    else:
        print(f"data_type {ans} does not have a regex")


def save_new_header(curr_header, new_header):
    """Like the name says.

    :param h.Header curr_header: current header
    :param h.Header new_header: new header
    """
    for i in range(new_header.num_fields):
        if new_header.fields[i].name in [chf.name for chf in curr_header.fields]:
            copy_curr_to_new_header(curr_header, new_header, i)
        else:
            create_new_header_rules(new_header, i)
    print("Not saving new header at this time")


def manage_cu_header_rules():
    curr_header = h.Header(json_file="cu_download_format.json")
    with open("downloads/ExportedTransactions.csv", "r") as f:
        new_header_field_names = f.readline().strip().replace('"', '').split(',')
    new_header = h.Header(field_name_list=new_header_field_names)
    differences = print_curr_vs_new_header_field_names(curr_header, new_header)

    if differences:
        ans = input("Would you like to save the new header? (y/n) ")
        if ans.lower() in ["yes", "y"]:
            save_new_header(curr_header, new_header)
    else:
        print("No differences - not saving")


def manage_citi_header_rules():
    curr_header = h.Header(json_file="citi_download_format.json")
    with open("downloads/Citi-RecentActivity.CSV", "r") as f:
        new_header_field_names = f.readline().strip().replace('"', '').split(',')
    new_header = h.Header(field_name_list=new_header_field_names)
    print_curr_vs_new_header_field_names(curr_header, new_header)


def manage_discover_header_rules():
    curr_header = h.Header(json_file="discover_download_format.json")
    with open("downloads/Discover-RecentActivity.csv", "r") as f:
        new_header_field_names = f.readline().strip().replace('"', '').split(',')
    new_header = h.Header(field_name_list=new_header_field_names)
    print_curr_vs_new_header_field_names(curr_header, new_header)


if len(sys.argv) != 2 or sys.argv[1] not in ["cu", "citi", "discover"]:
    print(f"Usage: {sys.argv[0]} cu|citi|discover")
    sys.exit(1)

source = sys.argv[1]
if source == "cu":
    manage_cu_header_rules()
elif source == "citi":
    manage_citi_header_rules()
else:
    manage_discover_header_rules()

print("All done.")
