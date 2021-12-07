pathtype: convert client arguments to Path instances
===

The *pathtype* Python package makes it easy to convert command line path 
arguments to [`pathlib.Path`](https://docs.python.org/3/library/pathlib.html) 
instances. It also provides multiple validations to easily and 
automatically validate paths when parsing arguments.

The package provides a `Path` class that can be used as `type` with the 
`argparse` package.

**Example:**

```python
import argparse
import pathtype

parser = argparse.ArgumentParser()

# Create a new --path argument using the `pathtype.Path` class
parser.add_argument("--path", type=pathtype.Path())
```

When parsing command line arguments with the above parser, `args.path` will now
contain a `pathlib.Path` instance initialized with the value of the `--path` 
argument:

```python
args = parser.parse_args(["--path", "/path/to/my_file.txt"])
print(args.path.stem)
# >>> "my_file"
```

## Validations

It's not doing much just like that. The class can also run various 
validations on the path or the file the path points to. This moves 
validation logic from your code to the arguments parsing. Once the parsing 
completes, you know the path you received passed validations.

For example, you can validate that the path points to an existing file or 
directory. Running this script:

```python
parser.add_argument("--path", type=pathtype.Path(exists=True))
# Try to pass a path to a non-existent file
args = parser.parse_args(["--path", "/non/existent/file.txt"])
```
will end the script with the following error:
```
usage: myscript.py [-h] [--path PATH]
myscript.py: error: argument --path: path doesn't exist: /non/existent/file.txt
```

For the various predefined validations, see description of the
``pathtype.Path`` class.

### Custom validation

You can also add your own validation. Pass to the `validator` parameter one 
or more functions (or callbacks). They will be called in order and if any 
raises a `argparse.ArgumentTypeError`, `TypeError`, or `ValueError`, the 
argument parsing will end in error.

For example, the following custom validation validates that the path is for 
a file with name `my_file.txt`:

```python
import pathlib
import argparse
import pathtype


def validate_file_name(path: pathlib.Path, arg: str):
    if path.name != "my_file.txt":
        raise argparse.ArgumentTypeError(f"invalid file name ({path.name})")

parser = argparse.ArgumentParser()

parser.add_argument("--path", type=pathtype.Path(validator=validate_file_name))

# We try to parse invalid arguments
args = parser.parse_args(["--path", "/path/to/image.jpg"])
```

Running this script ends with the following error message:
```
usage: myscript.py [-h] [--path PATH]
myscript.py: error: argument --path: invalid file name (image.jpg)
```

You can also create more complex validations using the ``validation.Any`` and
``validation.All`` classes. The first one accepts multiple validations and
validates as soon as any of its child validations validates. The second also 
accepts multiple validations and validates only if all of its child 
validations validate.