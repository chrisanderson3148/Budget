#!/usr/local/bin/python3
from os import path
import sys
import os
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


def copy_curr_rules_to_new_header(curr_header, new_header, i):
    """Like the name says.

    :param h.Header curr_header: current header
    :param h.Header new_header: new header
    :param int i: index of both curr and new header field"""
    for j in range(curr_header.num_fields):
        if curr_header.fields[j].name == new_header.fields[i].name:
            new_header.fields[i].set_data_type(curr_header.fields[j].data_type)
            new_header.fields[i].set_regex(curr_header.fields[j].regex)
            print(f"Copied curr_header field {j} to new_header field {i}")
            break


def copy_new_header_field_rules(curr_header, new_header):
    """Copy field rules from curr_header for new_header fields with matching names

    :param h.Header curr_header: current header
    :param h.Header new_header: new header
    """
    # Go through each new header field and copy current field rules for fields with matching names
    for i in range(new_header.num_fields):
        if new_header.fields[i].name in [chf.name for chf in curr_header.fields]:
            copy_curr_rules_to_new_header(curr_header, new_header, i)


def manage_header_rules(json_file_name, downloads_file_name):
    curr_header = h.Header(json_file=json_file_name)
    with open(f"downloads/{downloads_file_name}", "r") as f:
        new_header_field_names = f.readline().strip().replace('"', '').split(',')
    new_header = h.Header(field_name_list=new_header_field_names)
    print_curr_vs_new_header_field_names(curr_header, new_header)

    # Copy over field rules from current header matching fields name
    copy_new_header_field_rules(curr_header, new_header)

    ans = input("Would you like to save the new header? (y/n) ")
    if ans.lower() in ["yes", "y"]:
        print("First edit the new header field rules")
        new_header.edit_header()
        new_header.save_header(json_file_name)
        print(f"{json_file_name} saved (old json file renamed)")


if len(sys.argv) != 2 or sys.argv[1] not in ["cu", "citi", "discover"]:
    print(f"Usage: {sys.argv[0]} cu|citi|discover")
    sys.exit(1)

source = sys.argv[1]
if source == "cu":
    manage_header_rules("cu_download_format.json", "ExportedTransactions.csv")
elif source == "citi":
    manage_header_rules("citi_download_format.json", "Citi-RecentActivity.CSV")
else:
    manage_header_rules("discover_download_format.json", "Discover-RecentActivity.csv")

print("All done.")
