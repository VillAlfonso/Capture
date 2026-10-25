"""Filename checks shared by the suite builders."""
import ntpath


def validate_name(value):
    value = value.strip()
    if not value or ntpath.isreserved(value) or any(c in value for c in '/\\'):
        raise ValueError('Enter a valid Windows filename without a folder path.')
    return value
