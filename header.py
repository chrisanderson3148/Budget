import json
import re


class FieldRule(object):
    """Object of field rules, including name.

    :param str name: Name of the field
    :param str data_type: Can be one of ["int", "float", "date", "str", "freestr"], defaults to ""
    :param str regex: A regular expression to validate the data field, defaults to ""
    """
    def __init__(self, name, data_type="", regex=""):
        self._name = name
        self._regex = regex
        self._data_type = data_type

    @property
    def name(self):
        return self._name

    @property
    def data_type(self):
        return self._data_type

    @property
    def regex(self):
        return self._regex

    def set_data_type(self, data_type):
        self._data_type = data_type

    def set_regex(self, regex):
        self._regex = regex

    def __repr__(self):
        return f"{{ name: '{self._name}', data_type: '{self._data_type}', regex: '{self._regex}' }}"


class Header(object):
    """Create a header object.

    :param str json_file: name of json file of header json to populate the object
    :param list[str] field_name_list: list of header field names to start populating the object
    """
    def __init__(self, json_file=None, field_name_list=None):
        self._num_fields = 0
        self._fields = []

        assert not (json_file and field_name_list), "Cannot provide both json_file and field_name_list"
        if json_file:
            with open(json_file, "r") as f:
                field_dict = json.load(f)
            for field in field_dict['field_types']:
                if 'regex' in field:  # 'regex' is optional for some types
                    self._fields.append(FieldRule(field['name'], data_type=field['data_type'], regex=field['regex']))
                else:
                    self._fields.append(FieldRule(field['name'], data_type=field['data_type']))
                self._num_fields += 1
        elif field_name_list:
            for field_name in field_name_list:
                self._fields.append(FieldRule(field_name))
                self._num_fields += 1

    @property
    def num_fields(self):
        return self._num_fields

    @property
    def fields(self):
        return self._fields

    def validate_header_field_names(self, list_of_field_names):
        """Validate a list of field names against the rules.

        :param list[str] list_of_field_names: list of field names to validate
        """
        assert len(list_of_field_names) == self._num_fields, (
            f"Length of field names {len(list_of_field_names)} is not same as number of expected fields "
            f"{self._num_fields}")
        for i in range(self._num_fields):
            assert list_of_field_names[i] == self._fields[i].name, (
                f"Field name did not match: '{list_of_field_names[i]}' should be '{self._fields[i].name}'")

    def validate_data_field_values(self, list_of_field_values):
        """Validate a list of field values against the rules.

        :param list[str] list_of_field_values: List of field values
        """
        assert len(list_of_field_values) == self._num_fields, (
            f"The length of data fields {len(list_of_field_values)} is not the same as the number of expected fields "
            f"{self._num_fields}")
        for i in range(self._num_fields):
            if self._fields[i].data_type == "freestr":
                pass
            else:
                assert re.match(self._fields[i].regex, list_of_field_values[i]), (
                    f"Field {i} value {list_of_field_values[i]} did not validate from regex {self._fields[i].regex}")

    def __repr__(self):
        rstr = "header = {\n  field_types: ["
        for field in self._fields:
            rstr += f"\n    {field},"
        rstr += "\n  ]\n}"
        return rstr
