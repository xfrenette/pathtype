import collections.abc
import pathlib
from typing import List, Optional, Pattern, Union

from . import validation as val

# noinspection PyProtectedMember
_Validations = val._Validations
# noinspection PyProtectedMember
_ValidationCallable = val._ValidationCallable


class Path:
    """
    `argparse` type that parses an argument as a `Path` and validates it.

    Use an instance of this class as the ``type`` parameter in a
    ``argparse.ArgumentParser`` argument to convert a string argument to an instance
    of ``pathlib.Path``. The class also provides various validations that you can use
    to validate the path or the file (or directory) it points to. Using validations
    allows you to move path and file validations from your code to the argument parser.

    **Example**:

    >>> import pathtype
    >>> import argparse
    >>>
    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument("--path", type=pathtype.Path())

    Validations
    ============

    A variety of predefined validations are available to validate the path or the
    file (or directory) being referenced during argument parsing. Note that you can
    also add your own validations (see below).

    The following parameters trigger predefined validations and generate meaningful
    error messages when validation fails. If the path points to a symbolic link,
    all validations are run on the linked file, not the link itself.

    ``exists`` (boolean, default: `False`)
        If ``True``, validates that the path points to an existing file or directory.
        If the user doesn't have the required permissions to validate its existence (
        e.g. the user doesn't have the "execute" permission on the parent directory),
        an error is raised. Note that some other predefined validations imply
        ``exists`` (ex: ``readable``). In those cases, you don't need to specify it.

    ``not_exists`` (boolean, default: `False`)
        If ``True``, validates that the path points to a non-existing file or
        directory. If the user doesn't have the required permissions to validate its
        existence (e.g. the user doesn't have the "execute" permission on the parent
        directory), an error is raised. You cannot have both `not_exists` and
        `exists` set to True (or any other validation that imply `exists=True`). An
        error is raised in that case.

    ``readable`` (boolean, default: `False`)
        If ``True``, validates that the user has "read" access on the file or
        directory pointed by the path. Implies ``exists=True``.

    ``writable`` (boolean, default: `False`)
        If ``True``, validates that the user has "write" access on the file or
        directory pointed by the path. Implies ``exists=True``.

    ``executable`` (boolean, default: `False`)
        If ``True``, validates that the user has "execute" access on the file or
        directory pointed by the path. Implies ``exists=True``.

    ``parent_exists`` (boolean, default: `False`)
        If ``True``, validates that the direct parent directory of the path exists.
        If the user doesn't have the required permissions to validate its existence
        (e.g. the user doesn't have the "execute" permission on the parent directory's
        parent), an error is raised. This validation is ignored if ``exists`` (or any
        other validation that implies it) is set to ``True``. See documentation of
        ``validation.ParentExists`` for a remark about symbolic links.

    ``creatable`` (boolean, default: `False`)
        If ``True``, validates that the current user has "write" permission on the
        direct parent directory of the path. This validation is generally used to
        validate that the user can create the file or directory at the path. Be
        warned that only the "write" permission is checked at argument parsing time.
        Other restrictions might prevent the user from actually creating the file,
        and the "write" permission may change after the check. The validation doesn't
        check if the path already points to an existing file or directory. The parent
        directory must already exist though, so this validation implies
        ``parent_exists=True``. If you want to validate that the file can be created
        *or*, if it exists, that the user has "write" permission on it,
        check ``writable_or_creatable``.

    ``writable_or_creatable`` (boolean, default: `False`)
        If ``True``, equivalent to ``writable`` if the path points to an existing
        file or directory, else equivalent to ``writable``. This more complex
        validation can be used, for example, to validate that we can write in a file
        or, if it doesn't exist, that we will be able to create it to then write in
        it. See both ``writable`` and ``creatable`` for details. Cannot be used
        together with ``writable`` or ``creatable``.

    ``name_matches_re`` (String or compiled regular expression pattern, default: None)
        If a string, uses it as a regular expression pattern and validates that it
        matches the name part of the path. If a compiled regular expression pattern,
        uses it for the match. If None, skips this validation. The pattern is
        searched anywhere in the name, not only at the begining. So the pattern
        `"test"` would be found in the name ``my_test_file.txt``, while `"^test"`
        would not. The name part of the path is what is frequently called the "file
        name", including any extension. For example, the name in the path
        ``/path/to/my_file.tmp.txt`` is ``my_file.tmp.txt``. Note that some paths
        don't have a name, like the Windows path `C:/`. If you prefer to use glob
        patterns (ex: "*.txt"), see ``name_matches_glob``.

    ``name_matches_glob`` (String, default: None)
        If a string, validates that the name part of the path matches this glob. If
        None, skips this validation. More information about globs can be
        [found here](https://docs.python.org/3/library/fnmatch.html). The name part
        of the path is what is frequently called the "file name", including any
        extension. For example, the name in the path ``/path/to/my_file.tmp.txt`` is
        ``my_file.tmp.txt``. If you prefer to use regular expressions
        (ex: "[a-b]+]"), see ``name_matches_re``.

    ``path_matches_re`` (String or compiled regular expression pattern, default: None)
        Same as ``name_matches_re``, but validates the whole path, not just the name.
        The full, absolute path is validated, even if just a relative path was
        supplied.

    ``path_matches_glob`` (String, default: None)
        Same as ``name_matches_glob``, but validates the whole path, not just the
        name. The full, absolute path is validated, even if just a relative path was
        supplied.

    **Example**:

    >>> import pathtype
    >>> import argparse
    >>>
    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument(
    >>>     "--path",
    >>>     type=pathtype.Path(readable=True, writable=True)
    >>> )

    Custom validations
    ------------------

    You can also provide custom validation by passing to the ``validator`` parameter
    a "validator" (a function or a callback), or an iterable of validators.

    Each validator must have the following signature::

        validator(path: pathlib.Path, arg: str) -> None

    The first argument received by the validator is the ``pathlib.Path`` instance
    created from the argument string. The second argument is the argument string
    itself.

    If the validator validates, it shouldn't do anything. If it doesn't validate,
    it should raise one of the following error: ``argparse.ArgumentTypeError``,
    ``TypeError``, or ``ValueError``. Raising any other type of error won't be nicely
    handled by ``argparse``.

    Example: we add a custom validator to validate that the path is for a file named
    "my_file.txt":

    >>> import pathtype
    >>> import argparse
    >>>
    >>> def validate_is_my_file(path: pathlib.Path, arg: str):
    >>>     if path.name != "my_file.txt":
    >>>         raise argparse.ArgumentTypeError(f"invalid file name ({path.name})")
    >>>
    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument("--path", type=pathtype.Path(validator=validate_is_my_file))

    If custom validators are used in conjonction with predefined validators (for
    example if you use ``exists`` with a validator in ``validator``), predefined
    validators will *always run first*, before the custom ones.

    If you want to control the order of execution, you have to create your own
    sequence of validators. It's easy to use any of the predefined validators in your
    sequence. All predefined validators are available in the ``pathtype.validation``
    module. You can use any of them in your custom sequences.

    The following table lists the validation parameters of the class and the
    associated validation class (found in ``pathtype.validation``):

    .. csv-table::
       :header: "Parameter", "Validation class"

       "``exists``", "``Exists``"
       "``not_exists``", "``NotExists``"
       "``readable``", "``UserReadable``"
       "``writable``", "``UserWritable``"
       "``executable``", "``UserExecutable``"
       "``parent_exists``", "``ParentExists``"
       "``name_matches_re``", "``NameMatches``"
       "``name_matches_glob``", "``NameMatches``"
       "``path_matches_re``", "``PathMatches``"
       "``path_matches_glob``", "``PathMatches``"

    For example, if you want to first validate the directory name before validating
    that user has "write" access, you could do it like this:

    >>> import pathtype
    >>> import pathtype.validation as validation
    >>> import argparse
    >>>
    >>> def validate_directory_name(path: pathlib.Path, arg: str):
    >>>     if path.name != "my_dir":
    >>>         raise argparse.ArgumentTypeError(f"invalid name ({path.name})")
    >>>
    >>> validators = [validate_directory_name, validation.UserWritable()]
    >>>
    >>> parser = argparse.ArgumentParser()
    >>> # We don't use the `exists=True` parameter
    >>> parser.add_argument("--path", type=pathtype.Path(validator=validators))
    """

    def __init__(
        self,
        *,
        validator: Optional[_Validations] = None,
        exists=False,
        not_exists=False,
        readable=False,
        writable=False,
        executable=False,
        parent_exists=False,
        creatable=False,
        writable_or_creatable=False,
        name_matches_re: Optional[Union[str, Pattern]] = None,
        name_matches_glob: Optional[str] = None,
        path_matches_re: Optional[Union[str, Pattern]] = None,
        path_matches_glob: Optional[str] = None
    ):
        """
        :param validator: Callable, or iterable of callables, that validate the Path
            and raise an exception if validation fails.
        :param exists: If True, validate that the path points to an existing file
        :param not_exists: If True, validate that the path doesn't point to an
            existing file
        :param readable: If True, validate that the user has "read" permission on the
            pointed file. Implies `exists=True`.
        :param writable: If True, validate that the user has "write" permission on
            the pointed file. Implies `exists=True`.
        :param executable: If True, validate that the user has "execute" permission
            on the pointed file. Implies `exists=True`.
        :param parent_exists: If True, validate that the direct parent directory of
            the path exists
        :param creatable: If True, validate that the parent directory exists and that
            the user has "write" permission on it.
        :param writable_or_creatable: If True, equivalent to ``writable`` if the path
            exists, else equivalent to ``creatable``.
        :param name_matches_re: Regular expression string or compiled pattern to
            compare against the name part of the path. Ignored if None.
        :param name_matches_glob: Glob string to compare against the name part of the
            path. Ignored if None.
        :param path_matches_re: Regular expression string or compiled pattern to
            compare against the absolute path. Ignored if None.
        :param path_matches_glob: Glob string to compare against the absolute the path.
            Ignored if None.
        """
        validations: List[_ValidationCallable] = []

        if writable or readable or executable:
            exists = True

        if writable_or_creatable:
            writable = False
            creatable = False

        if exists and not_exists:
            raise ValueError("`exists` and `not_exists` cannot both be True")

        if exists:
            validations.append(val.Exists())

        if not_exists:
            validations.append(val.NotExists())

        if readable:
            validations.append(val.UserReadable())
        if writable:
            validations.append(val.UserWritable())
        if executable:
            validations.append(val.UserExecutable())

        if creatable:
            parent_exists = True

        if parent_exists and not exists:
            validations.append(val.ParentExists())

        if creatable:
            validations.append(val.ParentUserWritable())

        if writable_or_creatable:
            writable_validation = val.All(val.Exists(), val.UserWritable())
            creatable_validation = val.All(val.ParentExists(), val.ParentUserWritable())
            validations.append(val.Any(writable_validation, creatable_validation))

        if name_matches_re is not None and name_matches_glob is not None:
            raise ValueError(
                "cannot use both `name_matches_re` and `name_matches_glob`"
            )

        if name_matches_re is not None:
            validations.append(val.NameMatches(pattern=name_matches_re))

        if name_matches_glob is not None:
            validations.append(val.NameMatches(glob=name_matches_glob))

        if path_matches_re is not None and path_matches_glob is not None:
            raise ValueError(
                "Cannot use both `path_matches_re` and `path_matches_glob`."
            )

        if path_matches_re is not None:
            validations.append(val.PathMatches(pattern=path_matches_re))

        if path_matches_glob is not None:
            validations.append(val.PathMatches(glob=path_matches_glob))

        # Any custom validation
        if validator is not None:
            if isinstance(validator, collections.abc.Iterable):
                validations.extend(validator)
            else:
                validations.append(validator)

        self.validations: List[_ValidationCallable] = validations

    def __call__(self, arg: str) -> pathlib.Path:
        """
        Convert the string argument to a Path instance and validate it.

        This method is called by ``argparse`` when parsing the argument. The raw
        string argument is passed. It is first converted to a ``pathlib.Path``
        instance and then all validators are executed in order (each receiving the
        ``pathlib.Path`` instance and the original argument). Any of the validator
        can raise an exception, which should be of type
        ``argparse.ArgumentTypeError``, ``TypeError``, or ``ValueError``. In any
        case, exceptions will be passed through to ``argparse`` which will handled
        them. If no exception were raised, the ``pathlib.Path`` instance is returned.

        :param arg: Raw argument string
        :return: The ``pathlib.Path`` instance
        """
        path = pathlib.Path(arg)

        for validation in self.validations:
            validation(path, arg)

        return path
