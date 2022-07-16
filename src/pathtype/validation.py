import abc
import argparse
import fnmatch
import os
import pathlib
import re
from typing import Callable, Iterable, Optional, Pattern, Union

_ValidationCallable = Callable[[pathlib.Path, str], None]
_Validations = Union[_ValidationCallable, Iterable[_ValidationCallable]]
_RE_Error = type(re.error(""))


class _SimpleValidation:
    def __eq__(self, other):
        if self is other:
            return True

        return type(self) == type(other)


class _LogicalValidation:
    def __init__(self, *validations: _ValidationCallable):
        """
        :param validations: validators to execute
        """
        self.validations = validations

    def __eq__(self, other: object):
        if not isinstance(other, type(self)):
            return NotImplemented

        if len(self.validations) != len(other.validations):
            return False

        for self_val, other_val in zip(self.validations, other.validations):
            if self_val != other_val:
                return False

        return True


class Any(_LogicalValidation):
    """
    Container of validators that validates if any of its validators succeeds.

    Child validators are run sequentially. At the first that succeeds (doesn't raise
    any exception), this validator container immediately ends (validation passed).
    Subsequent child validators are not executed.

    If all child validators failed *and* they all raised a supported exception
    (``argparse.ArgumentTypeError``, ``TypeError`` or ``ValueError``) the exception
    raised by the last children will be raised by this container.

    If any child validator raises an unsupported exception, execution of subsequent
    child validators is halted and the raised exception raises to the caller.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        managed_exceptions = (argparse.ArgumentTypeError, TypeError, ValueError)
        last_exception: Optional[BaseException] = None

        for validation in self.validations:
            try:
                validation(path, arg)
                # We stop at the first validator that passes
                return
            except managed_exceptions as exception:
                last_exception = exception

        raise last_exception  # type: ignore[misc]


class All(_LogicalValidation):
    """
    Container of validators that validates if all of its validators succeeds.

    Child validators are run sequentially. At the first that fails (raises any
    exception), this validator container immediately ends and re-raises the
    exception. Subsequent child validators are not executed.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        for validation in self.validations:
            validation(path, arg)


class Exists(_SimpleValidation):
    """
    Validator that checks that the path points to an existing object.

    If the path doesn't point to an existing file or directory,
    an ``argparse.ArgumentTypeError`` error is raised.

    If the user doesn't have the permissions to check the existence of the path (for
    example, if the user doesn't have the "execute" permission on the parent
    directory), an error is raised.

    If the path points to a symbolic link, the existence is checked on the linked
    file, not on the link itself.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        try:
            if not path.exists():
                raise argparse.ArgumentTypeError(f"file doesn't exist ({arg})")
        except PermissionError:
            raise argparse.ArgumentTypeError(
                f"not enough permissions to validate existence of file ({arg})"
            )


class NotExists(_SimpleValidation):
    """
    Validator that checks that the path points to a non-existent object.

    If the path points to an existing file or directory, an
    ``argparse.ArgumentTypeError`` error is raised.

    If the user doesn't have the permissions to check the existence of the path (for
    example, if the user doesn't have the "execute" permission on the parent
    directory), an error is raised.

    If the path points to a symbolic link, the existence is checked on the linked
    file, not on the link itself.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        try:
            if path.exists():
                raise argparse.ArgumentTypeError(f"file already exists ({arg})")
        except PermissionError:
            raise argparse.ArgumentTypeError(
                f"not enough permissions to validate existence of file ({arg})"
            )


class UserReadable(_SimpleValidation):
    """
    Validator that checks that the user has "read" access on the pointed file.

    If the user doesn't have read access to the file or the directory at the path,
    an ``argparse.ArgumentTypeError`` error is raised.

    The "user" is the user currently running the script. Different scenarios allow
    read access to the user, not just "the user is the owner of the file, and they
    have read permission". For example, the user might be in a group that has read
    permission on the pointed file. In that case, this validator would success.

    If the path points to a symbolic link, the access is checked on the linked file,
    the on the link itself.

    This validator doesn't first check that the path points to an existing file or
    directory. If it doesn't exist, or if information about the file cannot be
    determined (for example, if the user doesn't have the "execute" access on the
    parent directory), the result is undefined and is platform dependent. It could
    raise a `FileNotFoundError`` error, or it could simply consider the file as not
    readable. So generally, you would run this validator after ``Exists``.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        if not os.access(path, os.R_OK):
            raise argparse.ArgumentTypeError(
                f"you don't have read permission on file ({arg})"
            )


class UserWritable(_SimpleValidation):
    """
    Validator that checks that the user has "write" access on the pointed file.

    If the user doesn't have write access to the file or the directory at the path,
    an ``argparse.ArgumentTypeError`` error is raised.

    The "user" is the user currently running the script. Different scenarios allow
    write access to the user, not just "the user is the owner of the file, and they
    have write permission". For example, the user might be in a group that has write
    permission on the pointed file. In that case, this validator would success.

    If the path points to a symbolic link, the access is checked on the linked file,
    the on the link itself.

    This validator doesn't first check that the path points to an existing file or
    directory. If it doesn't exist, or if information about the file cannot be
    determined (for example, if the user doesn't have the "execute" access on the
    parent directory), the result is undefined and is platform dependent. It could
    raise a `FileNotFoundError`` error, or it could simply consider the file as not
    writable. So generally, you would run this validator after ``Exists``.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        if not os.access(path, os.W_OK):
            raise argparse.ArgumentTypeError(
                f"you don't have write permission on file ({arg})"
            )


class UserExecutable(_SimpleValidation):
    """
    Validator that checks that the user has "execute" access on the file.

    If the user doesn't have execute access to the file or the directory at the path,
    an ``argparse.ArgumentTypeError`` error is raised.

    The "user" is the user currently running the script. Different scenarios allow
    execute access to the user, not just "the user is the owner of the file, and they
    have execute permission". For example, the user might be in a group that has
    execute permission on the pointed file. In that case, this validator would success.

    If the path points to a symbolic link, the access is checked on the linked file,
    the on the link itself.

    This validator doesn't first check that the path points to an existing file or
    directory. If it doesn't exist, or if information about the file cannot be
    determined (for example, if the user doesn't have the "execute" access on the
    parent directory), the result is undefined and is platform dependent. It could
    raise a `FileNotFoundError`` error, or it could simply consider the file as not
    executable. So generally, you would run this validator after ``Exists``.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path to validate
        :param arg: Raw string value of the argument
        """
        if not os.access(path, os.X_OK):
            raise argparse.ArgumentTypeError(
                f"you don't have execute permission on file ({arg})"
            )


class ParentExists(_SimpleValidation):
    """
    Validator that checks that the direct parent directory of the path exists.

    If the parent directory of the path doesn't exist, of if the path has no parent
    (e.g. the root directory has no parent), an ``argparse.ArgumentTypeError`` error
    is raised.

    If the user doesn't have the permissions to check the existence of the parent
    (for example, if the user doesn't have the "execute" permission on the parent
    directory's parent), an error is raised.

    To determine the parent, this class first resolves any symbolic link and up-level
    references (ex: ../). It then checks the existence of the resulting path's parent
    directory. So the parent that is checked is:

        >>> path: pathlib.Path = # ...
        >>> parent = path.resolve().parent

    In particular, this means that if the path points to a symbolic link, the parent
    will be the directory containing the linked file, not the directory containing
    the symbolic link itself. Also, any symbolic link in the parent's path will be
    resolved.
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
                f"file doesn't have a parent directory ({arg})"
            )

        try:
            if not parent.exists():
                raise argparse.ArgumentTypeError(
                    f"file's parent directory doesn't exist ({arg})"
                )
        except PermissionError:
            raise argparse.ArgumentTypeError(
                f"not enough permissions to validate existence of file's parent "
                f"directory ({arg})"
            )


class ParentUserWritable(_SimpleValidation):
    """
    Validator that checks that the user has "write" permission on the parent
    directory of the path.

    If the user doesn't have "write" permission on the parent directory of the path,
    an ``argparse.ArgumentTypeError`` error is raised.

    This validator is generally used to check if it's possible to create the
    specified file or directory, since having "write" permission on the parent
    directory is required. It's not enough though, and if this validation passes it
    doesn't guarantee that the user is actually allowed to create the file or
    directory.

    The "user" is the user currently running the script. Different scenarios allow
    "write" access to the user, not just "the user is the owner of the parent
    directory, and they have "write" permission". For example, the user might be in a
    group that has "write" permission on the parent directory. In that case,
    this validator would success.

    This validator doesn't first check that the parent directory exists. If it
    doesn't exist, or if information about the directory cannot be determined (for
    example, if the user doesn't have the "execute" access on the grandparent
    directory to determine the parent directory's access), the result is undefined
    and is platform dependent. It could raise a `FileNotFoundError`` error,
    or it could simply consider the file as not writable. So generally, you would run
    this validator after ``ParentExists``. Also note that the parent of the root
    directory is itself, which might give unexpected results. Once again, executing
    the ``ParentExists`` validator before this one prevents this problem.

    To determine the parent, this class first resolves any symbolic link and up-level
    references (ex: ../). It then checks the existence of the resulting path's parent
    directory. So the parent that is checked is:

        >>> path: pathlib.Path = # ...
        >>> parent = path.resolve().parent

    In particular, this means that if the path points to a symbolic link, the parent
    will be the directory containing the linked file, not the directory containing
    the symbolic link itself. Also, any symbolic link in the parent's path will be
    resolved.
    """

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path whose parent we want to validate
        :param arg: Raw string value of the argument
        """
        resolved = path.resolve()
        parent = resolved.parent

        if not os.access(parent, os.W_OK):
            raise argparse.ArgumentTypeError(
                f"you don't have write permission on the file's parent directory "
                f"({arg})"
            )


class PatternMatches(abc.ABC):
    """
    Abstract class to do pattern matching. See specific implementations (like
    NameMatches or PathMatches) for thorough documentation.
    """

    def __init__(
        self,
        *,
        pattern: Optional[Union[str, Pattern]] = None,
        glob: Optional[str] = None,
    ):
        """
        :param pattern: String or compiled regular expression
        :param glob: Glob pattern
        """
        self.pattern: Optional[Pattern] = None
        self.glob = glob

        if isinstance(pattern, Pattern):
            self.pattern = pattern
        elif pattern is not None:
            try:
                self.pattern = re.compile(pattern)
            except _RE_Error:
                raise ValueError(
                    f"could not compile regular expression pattern ({pattern})"
                )

        nb_none_patterns = sum(attr is None for attr in (self.pattern, self.glob))
        if nb_none_patterns != 1:
            raise ValueError("you must specify a pattern or a glob (only one)")

    @abc.abstractmethod
    def _get_subject_string(self, path: pathlib.Path, arg: str) -> str:
        """
        Return the string in which we have to perform the pattern search.

        :param path: Path we want to validate
        :param arg: Raw string value of the argument
        :return: String in which we want to search
        """
        raise NotImplementedError

    def __call__(self, path: pathlib.Path, arg: str):
        """
        :param path: Path we want to validate
        :param arg: Raw string value of the argument
        """
        subject = self._get_subject_string(path, arg)
        not_found = False
        message_match = ""

        if self.pattern is not None:
            if self.pattern.search(subject) is None:
                not_found = True
                message_match = f'pattern "{self.pattern.pattern}"'
        elif self.glob is not None:
            if not fnmatch.fnmatch(subject, self.glob):
                not_found = True
                message_match = f'glob "{self.glob}"'

        if not_found:
            raise argparse.ArgumentTypeError(f"{message_match} doesn't match {subject}")

    def __eq__(self, other: object):
        if self is other:
            return True

        if not isinstance(other, type(self)):
            return NotImplemented

        if self.pattern is not None:
            return self.pattern == other.pattern

        return self.glob == other.glob


class NameMatches(PatternMatches):
    """
    Validator that checks that the name part of the path matches a pattern.

    The name part of the path is what is frequently called the "file name", including
    any file extension, but excluding any drive and root. For example, in the path
    `/path/to/my_file.txt.tmp`, the name is `my_file.txt.tmp`. Note that some paths
    have an empty name, like this Windows path: `C:/`.

    The `pattern` is either a compiled regular expression, or a regular expression
    pattern string. The pattern will be searched anywhere in the name. So if it
    doesn't start with the "beginning of line" character (`^`), it can match
    anywhere. For example, the pattern `"test"` would match the name
    `my_test_file.txt`, while the pattern `"^test"` would not.

    Instead of a regular expression pattern, you can pass a glob pattern as the
    `glob` argument. Glob patterns are
    [described here](https://docs.python.org/3/library/fnmatch.html).

    You cannot specify both a `pattern` and a `glob`, but you must specify one of
    them. A `ValueError` would be raised in other cases.
    """

    def _get_subject_string(self, path: pathlib.Path, arg: str) -> str:
        return path.name


class PathMatches(PatternMatches):
    """
    Validator that checks that the absolute path matches a pattern.

    Before comparing the path to the pattern, the path is resolved: it's made
    absolute and any ".", "..", or "~" is resolved. The pattern is then compared to
    the resulting path.

    The `pattern` is either a compiled regular expression, or a regular expression
    pattern string. The pattern will be searched anywhere in the name. So if it
    doesn't start with the "beginning of line" character (`^`), it can match
    anywhere. For example, the pattern `"test"` would match the path
    `../path/to/a/test/file.txt`, while the pattern `"^test"` would not.

    Instead of a regular expression pattern, you can pass a glob pattern as the
    `glob` argument. Glob patterns are
    [described here](https://docs.python.org/3/library/fnmatch.html).

    Symbolic links are not followed. So if the path is a symbolic link, the path of
    the link will be checked, not the path of the linked file.This validator compares
    the whole absolute path. If you want to check only the file name (the last part),
    use NameMatches.

    You cannot specify both a `pattern` and a `glob`, but you must specify one of
    them. A `ValueError` would be raised in other cases.

    Note: this validator doesn't require the path to point to an existing file. But
    if it is called with a relative path (ex: "relative/path" or
    "../parent/relative/path"), the path is made absolute relative to the current
    working directory (CWD). If the CWD cannot be determined (ex: the current
    directory doesn't exist anymore), a FileNotFoundError may be raised.
    """

    def _get_subject_string(self, path: pathlib.Path, arg: str) -> str:
        expanded = os.path.expanduser(path)
        return os.path.abspath(expanded)
