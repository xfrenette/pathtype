pathtype: Validate paths in command line arguments
===


The *pathtype* Python package makes it simple to validate paths in command line (CLI)
arguments. It's made to be used with the `argparse` argument parser. It can validate 
the existence of the file, its permissions, its file name, file extension, etc. With 
*pathtype*, you keep path arguments validation inside the command line parsing logic,
away from your core application code.

Use it as the `type` argument in `parser.add_argument()` to automatically have a CLI 
path argument validated and returned as a `pathlib.Path` instance.

It works with Python 3.7+, both with Posix and Windows paths.

**Example**

```python
import argparse
import pathtype

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # We use `pathtype.Path` as the `type` argument to validate that the --image 
    # argument is a readable image file (checks the file extension).
    parser.add_argument(
        "--image", required=True,
        help="Image file to open (PNG, GIF or JPEG supported)",
        type=pathtype.Path(readable=True, name_matches_re=r"\.(png|jpe?g|gif)$")
    )
 
    # Path validations are done automatically by calling the next line, no need to 
    # add code to validate that the path can be read and that it has the correct 
    # extension. 
    args = parser.parse_args()
    
    # args.image is an instance of pathlib.Path. And since using `readable` implies 
    # `exists`, we know the file already exists and is readable by the current user.
    print(args.image.exists())
    # True
```

# Installation

*pathtype* requires Python 3.7+.

Install with pip:

```shell
pip install pathtype
```

# Usage

Using `pathtype.Path` without any arguments simply converts the CLI argument to a 
`pathlib.Path` instance:

```python
parser.add_argument(
  "my_arg", type=pathtype.Path()
)

args = parser.parse_args()
print(type(args.my_arg))  # >>> <class 'pathlib.PosixPath'>
```

But you will generally also want to run some validations on the properties of the path.

## Predefined validations (basic usage)

Multiple validations are available to have the path validated during CLI arguments 
parsing. If a validation fails, argument parsing will fail in the usual manner. If 
it succeeds, the argument will be converted to a `pathlib.Path` instance.

| To validate that...                                                      | use ...                                                        |
|--------------------------------------------------------------------------|----------------------------------------------------------------|
| the path points to an existing file or directory                         | `pathtype.Path(exists=True)`                                   |
| the path does NOT point to an existing file or directory                 | `pathtype.Path(not_exists=True)`                               |
| the path's parent directory exists                                       | `pathtype.Path(parent_exists=True)`                            |
| the file can be created (*)                                              | `pathtype.Path(creatable=True)`                                |
| the file can be created or, if it already exists, it's writable (*)      | `pathtype.Path(writable_or_creatable=True)`                    |
| the current user has some permissions on the file or directory (*)       | `pathtype.Path(readable=True, writable=True, executable=True)` |
| the *file name* (the last part of the path) matches a regular expression | `pathtype.Path(name_matches_re=r"\.jpe?g$")`                   |
| the *file name* matches a glob pattern                                   | `pathtype.Path(name_matches_glob="*.pkl")`                     |
| the *full* (absolute and normalized) path matches a regular expression   | `pathtype.Path(path_matches_re="/home/.+/logs/?$")`            |
| the *full* path matches a glob pattern                                   | `pathtype.Path(path_matches_glob="/home/*/*.pkl")`             |

(*) All permission related validations use the current user's permission. For example,
the `creatable` validation validates that the user running your code has permissions to 
create the file. Ignored on Windows.

### Combining validations

You can combine multiple validations together.

**Example**

Validate that the path is a text file (*.txt) that doesn't exist yet, but that the 
current user has permissions to create the file (implies that the parent directory 
exists):

```python
parser.add_argument(
    "--file",
    type=pathtype.Path(not_exists=True, creatable=True, name_matches_glob="*.txt")
)
args = parser.parse_args(["--file", "path/to/my_file.txt"])
```

# Custom validation (advanced usage)

You can also create your own custom validations (or "validators") and use them alone, 
or in combination with the predefined validations.

## Making a custom validator

A custom validator is a callable object (generally a function) that has the 
following signature:

```python
def validator(path: pathlib.Path, arg: str) -> None
```

The validator must accept two arguments, `path` and `arg`, that are two views of the 
original CLI argument. If the original CLI argument was `"../path/to/file"`, then
`path = pathlib.Path("../path/to/file")` and `arg = "../path/to/file"`.

If the validator considers that its validation failed, it must raise one of the
following exception:

* `argparse.ArgumentTypeError`
* `TypeError`
* `ValueError`

Raising any other type of error won't be nicely handled by ``argparse``.

If its validation passes, it must end without returning anything.

## Using a custom validator

You use the validator by passing it to the `validator` parameter of `pathtype.Path()`.

You can also pass an iterable (ex: a list) of validators, and they will be executed 
sequentially.

**Example**

The next example creates two (strange) custom validators: one that validates that the 
file name contains the letter "a", the other validates that the file name doesn't 
contain the letter "b". The command line argument *--path-1* uses only the first 
validator, the command line argument *--path-2* uses both.

```python
def must_have_a(path: pathlib.Path, arg: str):
    """Custom validator that fails if the file name doesn't contain the letter 'a'."""
    if "a" not in path.name:
        raise argparse.ArgumentTypeError('The file name must have the letter "a"')

def must_not_have_b(path: pathlib.Path, arg: str):
    """Custom validator that fails if the file name contains the letter 'b'."""
    if "b" in path.name:
        raise argparse.ArgumentTypeError('The file name must NOT have the letter "b"')

    
parser = argparse.ArgumentParser()
parser.add_argument(
    "--path-1",
    type=pathtype.Path(validator=must_have_a)
)
parser.add_argument(
    "--path-2",
    type=pathtype.Path(validator=[must_have_a, must_not_have_b])
)
```

## Using predefined validations with a custom validator

You can still use any of the predefined validations (as presented in the "basic 
usage" section) when using a custom validator.

**Example**

The following would validate the existence of the file and run a custom validator.

```python
parser.add_argument(
    ...
    type=pathtype.Path(validator=must_not_have_b, exists=True)
)
```

**Warning:** Validators in `validator` are always run *after* any of the predefined 
validations. So in the previous example, the existence of the file is validated 
*first* and only then the custom validator is executed.

If you need to change the order, you would have to remove `exists=True` and instead
add an "existence" validator to your list of custom validators, in the order you wish.

But you don't need to recreate validators for any of the predefined validations. They 
are all available in the `pathtype.validation` module. Just instantiate a class and 
use it like a custom validator.

**Example**

The following changes the order of validation of the previous example: first the 
custom validator is executed before validating the existence. The latter validator is
simply an instance of `pathtype.validation.Exists`.

```python
from pathtype.validation import Exists

exist_validator = Exists()

parser.add_argument(
    ...
    type=pathtype.Path(validator=[must_not_have_b, exist_validator])
)
```

## Logical combination of validators

The classes `pathtype.validation.Any` and `pathtype.validation.All` allow you to create
validators that are logical combinations of other validators (i.e. *OR* or *AND* 
expressions).

* `Any`: an instance of this class, initialized with a sequence of validators, is a 
  validator that will pass if *any* of its validators passes, and fail if they all 
  fail. Equivalent to an *OR* expression.
* `All`: Similarly, an instance of this class is a validator that will pass if *all* 
  of its validators pass, and fails if *any* fails. Equivalent to an *AND* expression.

Those two classes can be used to create complex validation trees.

**Example**

We create a validator that validates that the file name contains "a" *OR* that it 
doesn't contain "b":

```python
from pathtype.validation import Any

or_validator = Any(must_have_a, must_not_have_b)

parser.add_argument(
    ...
    type=pathtype.Path(validator=or_validator)
)
```

## Complete custom validator example

We want a custom validator that validates that the path is inside the current user's 
home directory:

```python
import os.path
import pathlib
import argparse
import pathtype


def is_inside_home_dir(path: pathlib.Path, arg: str):
    """Validate that the path is inside the current user's home directory."""
    expanded_path = os.path.expanduser(path)
    resolved_path = pathlib.Path(os.path.abspath(expanded_path))
    user_dir = pathlib.Path.home()
    # We check that `resolved_path` starts with the same directories as `user_dir`
    is_child = resolved_path.parts[:len(user_dir.parts)] == user_dir.parts
    
    if not is_child:
        raise argparse.ArgumentTypeError(
            f"path ({resolved_path}) is not in the user's home directory ({user_dir})"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        type=pathtype.Path(validator=is_inside_home_dir)
    )

    # The following line won't raise any error
    args = parser.parse_args(["--path", "~/valid/path"])
    print(repr(args.path))
    # PosixPath('~/valid/path')

    # The following line will fail since the path is not inside the user's directory
    args = parser.parse_args(["--path", "/at-root"])
    # Fails with this message:
    #   usage: example.py [-h] [--path PATH]
    #   example.py: error: argument --path: path (/at-root) is not in the user's home directory (/home/user)
```

# Notes

* All paths instances are actually
  [concrete paths](https://docs.python.org/3/library/pathlib.html#concrete-paths) 
  (i.e. created with `pathlib.Path()`), 
  and not pure paths (i.e. `pathlib.PurePath()`). This means that if ran on Windows, 
  the path argument will be converted to an instance of `pathlib.WindowsPath`, and on 
  other systems it'll be converted to an instance of `pathlib.PosixPath`. Behavior 
  may change on different OS's, so it's best not to parse argument across OS's.
* Validations are run once, during argument parsing. Always remember that, by the 
  time you actually use the path, some properties of the file may have changed. For 
  example, let's say you use `pathtype.Path(exists=True)`. Although the file may 
  exist at the time of argument parsing, another process may delete the file by the 
  time you actually want to access it. So only use this package as a user-friendly 
  "first check".