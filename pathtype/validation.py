import argparse
import os
import pathlib


class Exists:
    """
    Validator that checks that the path points to an existing object.

    If the path doesn't point to an existing file or directory,
    an ``argparse.ArgumentTypeError`` error is raised.

    If the user doesn't have the permissions to check the existence of the path
    (for example, if the user doesn't have the "execute" permission on the
    parent directory), an error is raised.

    If the path points to a symbolic link, the existence is checked on the
    linked file, not on the link itself.
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
            raise argparse.ArgumentTypeError(
                f"not enough permissions to validate existence of path: {arg}")


class NotExists:
    """
    Validator that checks that the path points to a non-existent object.

    If the path points to an existing file or directory, an
    ``argparse.ArgumentTypeError`` error is raised.

    If the user doesn't have the permissions to check the existence of the path
    (for example, if the user doesn't have the "execute" permission on the
    parent directory), an error is raised.

    If the path points to a symbolic link, the existence is checked on the
    linked file, not on the link itself.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        try:
            if path.exists():
                raise argparse.ArgumentTypeError(f"path exists: {arg}")
        except PermissionError:
            raise argparse.ArgumentTypeError(
                f"not enough permissions to validate existence of path: {arg}")


class UserReadable:
    """
    Validator that checks that the user has "read" access on the pointed file.

    If the user doesn't have read access to the file or the directory at the
    path, an ``argparse.ArgumentTypeError`` error is raised.

    The "user" is the user currently running the script. Different scenarios
    allow read access to the user, not just "the user is the owner of the
    file, and they have read permission". For example, the user might be
    in a group that has read permission on the pointed file. In that case,
    this validator would success.

    If the path points to a symbolic link, the access is checked on the
    linked file, the on the link itself.

    This validator doesn't first check that the path points to an existing
    file or directory. If it doesn't exist, or if information about the file
    cannot be determined (for example, if the user doesn't have the "execute"
    access on the parent directory), the result is undefined and is platform
    dependent. It could raise a `FileNotFoundError`` error, or it could
    simply consider the file as not readable. So generally, you would run
    this validator after ``Exists``.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        if not os.access(path, os.R_OK):
            raise argparse.ArgumentTypeError(f"path is not readable: {arg}")


class UserWritable:
    """
    Validator that checks that the user has "write" access on the pointed file.

    If the user doesn't have write access to the file or the directory at the
    path, an ``argparse.ArgumentTypeError`` error is raised.

    The "user" is the user currently running the script. Different scenarios
    allow write access to the user, not just "the user is the owner of the
    file, and they have write permission". For example, the user might be
    in a group that has write permission on the pointed file. In that case,
    this validator would success.

    If the path points to a symbolic link, the access is checked on the
    linked file, the on the link itself.

    This validator doesn't first check that the path points to an existing
    file or directory. If it doesn't exist, or if information about the file
    cannot be determined (for example, if the user doesn't have the "execute"
    access on the parent directory), the result is undefined and is platform
    dependent. It could raise a `FileNotFoundError`` error, or it could
    simply consider the file as not writable. So generally, you would run
    this validator after ``Exists``.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        if not os.access(path, os.W_OK):
            raise argparse.ArgumentTypeError(f"path is not writable: {arg}")


class UserExecutable:
    """
    Validator that checks that the user has "execute" access on the file.

    If the user doesn't have execute access to the file or the directory at the
    path, an ``argparse.ArgumentTypeError`` error is raised.

    The "user" is the user currently running the script. Different scenarios
    allow execute access to the user, not just "the user is the owner of the
    file, and they have execute permission". For example, the user might be
    in a group that has execute permission on the pointed file. In that case,
    this validator would success.

    If the path points to a symbolic link, the access is checked on the
    linked file, the on the link itself.

    This validator doesn't first check that the path points to an existing
    file or directory. If it doesn't exist, or if information about the file
    cannot be determined (for example, if the user doesn't have the "execute"
    access on the parent directory), the result is undefined and is platform
    dependent. It could raise a `FileNotFoundError`` error, or it could
    simply consider the file as not executable. So generally, you would run
    this validator after ``Exists``.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        if not os.access(path, os.X_OK):
            raise argparse.ArgumentTypeError(f"path is not executable: {arg}")


class ParentExists:
    """
    Validator that checks that the direct parent directory of the path exists.

    If the parent directory of the path doesn't exist, of if the path has no
    parent (e.g. the root directory has no parent),
    an ``argparse.ArgumentTypeError`` error is raised.

    If the user doesn't have the permissions to check the existence of the
    parent (for example, if the user doesn't have the "execute" permission on
    the parent directory's parent), an error is raised.

    To determine the parent, this class first resolves any symbolic link and
    up-level references (ex: ../). It then checks the existence of the resulting
    path's parent directory. So the parent that is checked is:

        >>> path: pathlib.Path = # ...
        >>> parent = path.resolve().parent

    In particular, this means that if the path points to a symbolic link,
    the parent will be the directory containing the linked file, not the
    directory containing the symbolic link itself. Also, any symbolic link in
    the parent's path will be resolved.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path whose parent we want to validate
        :param arg: Raw string value of the argument
        """
        resolved = path.resolve()
        parent = resolved.parent

        if parent == resolved:
            raise argparse.ArgumentTypeError(
                f"path doesn't have a parent directory: {arg}")

        try:
            if not parent.exists():
                raise argparse.ArgumentTypeError(
                    f"parent directory doesn't exist for path: {arg}")
        except PermissionError:
            raise argparse.ArgumentTypeError(
                f"not enough permissions to validate existence of parent of"
                f" path: {arg}")
