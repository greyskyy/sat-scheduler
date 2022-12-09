"""Methods used to augment argparse."""
import argparse


def positive_int(value):
    """Define an argument type to be a positive integer.

    Specify this as the `type` parameter to argparse's `add_argument`.

    Args:
        value (Any): The command line argument value

    Raises:
        argparse.ArgumentTypeError: The the value cannot be coerced into a positive integer.

    Returns:
        int: The argument value
    """
    intvalue = int(value)
    if intvalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return intvalue
