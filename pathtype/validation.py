import argparse
import pathlib


class PathExists:
    """
    Callback that validates that the path points to an existing object.

    Validates that the path points to an existing file or directory.

    If the user doesn't have the permissions to check if the path points to
    an existing file (if the user doesn't have "execute" permission on the
    parent directory, for example), the file is considered as not existing.

    If the path points to a symbolic link, the existence is checked on the
    linked file, the link.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        try:
            if not path.exists():
                raise argparse.ArgumentTypeError(f"path doesn't exist: {arg}")
        except PermissionError:
            raise argparse.ArgumentTypeError(f"not enough permissions to "
                                             f"access to path: {arg}")
