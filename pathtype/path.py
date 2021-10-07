import collections.abc
import pathlib
from typing import Callable, Iterable, List, Optional, Union

from . import validation as val

_ValidationCallable = Callable[[pathlib.Path, str], None]
_Validations = Union[_ValidationCallable, Iterable[_ValidationCallable]]


class Path:
    """
    `argparse` type that parses an argument as a Path and validates it.

    Use an instance of this class as the ``type`` parameter in a
    ``argparse.ArgumentParser`` argument to convert a string argument to an
    instance of ``pathlib.Path``. The class also provides various validations
    that you can use to validate the path or the file (or directory) it
    points to. Using validations allows you to move path and file validations
    from your code to the argument parser.

    **Example**:

    >>> import pathtype
    >>> import argparse
    >>>
    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument("--path", type=pathtype.Path())

    **********
    Validations
    **********

    A variety of predefined validations are available to validate the path or
    the file (or directory) being referenced during argument parsing. Note that
    you can also add your own validations (see below).

    The following parameters trigger predefined validations and generate
    meaningful error messages when validation fails. If the path points to a
    symbolic link, all validations are run on the linked file, not the link
    itself.

    ``exists`` (boolean, default: `False`)
        If ``True``, validates that the path points to an existing file or
        directory. If it exists, but the user doesn't have the required
        permissions to validate its existence (the user doesn't have
        execution permission on the parent directory, for example), the file
        is considered as not existing. Note that some other predefined
        validations imply ``exists`` (ex: ``readable``). In those cases,
        you don't need to specify it.
    ``readable`` (boolean, default: `False`)
        If True, validates that the user has "read" access on the file or
        directory pointed by the path. Implies ``exists``.
    ``writable`` (boolean, default: `False`)
        If True, validates that the user has "write" access on the file or
        directory pointed by the path. Implies ``exists``.
    ``executable`` (boolean, default: `False`)
        If True, validates that the user has "execute" access on the file or
        directory pointed by the path. Implies ``exists``.

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
    ----------

    You can also provide custom validation by passing to the ``validator``
    parameter a "validator" (a function or a callback), or an iterable of
    validators.

    Each validator must have the following signature::

        validator(path: pathlib.Path, arg: str) -> None

    The first argument received by the validator is the ``pathlib.Path``
    instance created from the argument string. The second argument is the
    argument string itself.

    If the validator validates, it shouldn't do anything. If it doesn't
    validate, it should raise one of the following error:
    ``argparse.ArgumentTypeError``, ``TypeError``, or ``ValueError``. Raising
    any other type of error won't be nicely handled by ``argparse``.

    Example: we add a custom validator to validate that the path is for a
    file named "my_file.txt":

    >>> import pathtype
    >>> import argparse
    >>>
    >>> def validate_file_is_my_file(path: pathlib.Path, arg: str):
    >>>     if path.name != "my_file.txt":
    >>>         raise argparse.ArgumentTypeError(f"invalid file name ({path.name})")
    >>>
    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument("--path", type=pathtype.Path(validator=validate_file_is_my_file))

    If custom validators are used in conjonction with predefined validators
    (for example if you use ``exists`` with a validator in ``validator``),
    predefined validators will *always run first*, before the custom ones.

    If you want to control the order of execution, you have to create your
    own sequence of validators. It's easy to use any of the predefined
    validators in your sequence. All predefined validators are available in
    the ``pathtype.validation`` module. You can use any of them in your
    custom sequences.

    The following table lists the validation parameters of the class and the
    associated validation class (found in ``pathtype.validation``):

    .. csv-table::
       :header: "Parameter", "Validation class"

       "``exists``", "``PathExists``"
       "``readable``", "``UserReadable``"
       "``writable``", "``UserWritable``"
       "``executable``", "``UserExecutable``"

    For example, if you want to first validate the directory name
    before validating that user has "write" access, you could do it like this:

    >>> import pathtype
    >>> import pathtype.validation as validation
    >>> import argparse
    >>>
    >>> def validate_directory_name(path: pathlib.Path, arg: str):
    >>>     if path.name != "my_dir":
    >>>         raise argparse.ArgumentTypeError(f"invalid directory name ({path.name})")
    >>>
    >>> validators = [validate_directory_name, validation.UserWritable()]
    >>>
    >>> parser = argparse.ArgumentParser()
    >>> # We don't use the `exists=True` parameter
    >>> parser.add_argument("--path", type=pathtype.Path(validator=validators))

    :param validator: Callable, or iterable of callables, that validate the
        Path and raise an exception if validation fails.
    :param exists: If True, add validation.PathExists to the list of validations
    :param readable: If True, add validation.Readable to the list of validations
    :param writable: If True, add validation.Writable to the list of validations
    :param executable: If True, add validation.Executable to the list of
        validations
    """

    def __init__(self, *, validator: Optional[_Validations] = None,
                 exists=False, readable=False, writable=False,
                 executable=False):
        validations = []

        # If `readable`, `writable` or `executable` is set, we automatically set
        # `exists`
        if writable or readable or executable:
            exists = True

        # The "exists" validation
        if exists:
            validations.append(val.PathExists())

        # The `readable`, `writable` and `executable` validations
        if readable:
            validations.append(val.UserReadable())
        if writable:
            validations.append(val.UserWritable())
        if executable:
            validations.append(val.UserExecutable())

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

        This method is called by ``argparse`` when parsing the argument. The
        raw string argument is passed. It is first converted to a
        ``pathlib.Path`` instance and then all validators are executed in
        order (each receiving the ``pathlib.Path`` instance and the original
        argument). Any of the validator can raise an exception, which should
        be of type ``argparse.ArgumentTypeError``, ``TypeError``,
        or ``ValueError``. In any case, exceptions will be passed through to
        ``argparse`` which will handled them. If no exception were raised,
        the ``pathlib.Path`` instance is returned.

        :param arg: Raw argument string
        :return: The ``pathlib.Path`` instance
        """
        path = pathlib.Path(arg)

        for validation in self.validations:
            validation(path, arg)

        return path
