import contextlib
import os
import sys
import tempfile
import unittest
from typing import Iterator


def symlink_test(cls_or_fn):
    """
    Decorator to mark a test class of function as testing symlink files.

    Such a test will be skipped on Windows.

    :param cls_or_fn: The class or function decorated.
    """
    platform_test = sys.platform.startswith("win")
    error_message = "Symlink tests skipped on Windows"

    return unittest.skipIf(platform_test, error_message)(cls_or_fn)


def access_permission_test(cls_or_fn):
    """
    Decorator to mark a test class of function as testing file permissions.

    Such a test will be skipped on Windows.

    :param cls_or_fn: The class or function decorated.
    """
    platform_test = sys.platform.startswith("win")
    error_message = "Access permission tests skipped on Windows"

    return unittest.skipIf(platform_test, error_message)(cls_or_fn)


@contextlib.contextmanager
def temp_dir_and_enter() -> Iterator[str]:
    """
    Context manager that creates a temporary dir and chdir into it, deleting it on exit.
    """
    cwd = os.getcwd()
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_dir_name = tmp_dir.name

    try:
        os.chdir(tmp_dir_name)
        yield tmp_dir_name
    finally:
        os.chdir(cwd)
        tmp_dir.cleanup()
