import argparse
import os
import pathlib
import re
import stat
import tempfile
import unittest
from typing import cast, Type, Union
from unittest import mock

import pathtype.validation as validation
from test.mixins import AccessTestCase, ArgparseTester, PatternMatcherTestCase
from test.utils import access_permission_test, symlink_test, temp_dir_and_enter


def _failing_validation(*args):
    raise argparse.ArgumentTypeError("Fail")


def _passing_validation(*args):
    # Do nothing
    pass


def _path_in_home_dir(path: Union[str, os.PathLike]) -> bool:
    path_to_check = pathlib.Path(path)
    home_dir = pathlib.Path.home()
    home_dir_parts = home_dir.parts
    return path_to_check.parts[: len(home_dir_parts)] == home_dir_parts


class TestAny(unittest.TestCase):
    """Tests for the "Any" validator."""

    def test_passes_if_any_passes(self):
        any_validator = validation.Any(
            _failing_validation,
            _passing_validation,
            _failing_validation,
        )
        # Shouldn't do anything
        any_validator(pathlib.Path("tmp"), "tmp")

    def test_fails_if_none_pass(self):
        any_validator = validation.Any(_failing_validation, _failing_validation)

        with self.assertRaises(argparse.ArgumentTypeError):
            any_validator(pathlib.Path("tmp"), "tmp")

    def test_returns_last_of_supported_exceptions(self):
        """
        If a validator raises one of the exceptions supported by argparse, the "any"
        validator should manage it and return the last one.
        """
        last_exception = TypeError("--Test exception--")

        def last_validator(*args):
            raise last_exception

        any_validator = validation.Any(_failing_validation, last_validator)

        with self.assertRaises(type(last_exception)) as raised_exception:
            any_validator(pathlib.Path("tmp"), "tmp")
            self.assertIs(last_exception, raised_exception)

    def test_doesnt_catch_other_exceptions(self):
        """
        If a validator raise any other exception not supported by argparse, it should
        be raised immediately.
        """
        last_exception = Exception("--Test exception--")

        def failing_validator(*args):
            raise last_exception

        any_validator = validation.Any(
            _failing_validation,
            failing_validator,
            _passing_validation,
        )

        with self.assertRaises(type(last_exception)) as raised_exception:
            any_validator(pathlib.Path("tmp"), "tmp")
            self.assertIs(last_exception, raised_exception)

    def test_equality(self):
        validator1 = validation.Any(validation.Exists(), validation.UserWritable())
        validator2 = validation.Any(validation.Exists(), validation.UserWritable())
        validator3 = validation.Any(validation.Exists())
        validator4 = validation.Any(validation.Exists(), validation.UserExecutable())

        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)
        self.assertNotEqual(validator1, validator3)
        self.assertNotEqual(validator1, validator4)


class TestAll(unittest.TestCase):
    def test_passes_if_all_pass(self):
        all_validator = validation.All(
            _passing_validation,
            _passing_validation,
            _passing_validation,
        )
        # Shouldn't do anything
        all_validator(pathlib.Path("tmp"), "tmp")

    def test_fails_if_any_fails(self):
        all_validator = validation.All(
            _passing_validation,
            _passing_validation,
            _failing_validation,
            _passing_validation,
        )

        with self.assertRaises(argparse.ArgumentTypeError):
            all_validator(pathlib.Path("tmp"), "tmp")

    def test_returns_first_exceptions(self):
        for ExceptionType in (TypeError, Exception):
            first_exception = ExceptionType("--Test exception--")

            def first_validator(*args):
                raise first_exception

            all_validator = validation.All(
                _passing_validation,
                first_validator,
                _failing_validation,
            )

            with self.assertRaises(ExceptionType) as raised_exception:
                all_validator(pathlib.Path("tmp"), "tmp")
                self.assertIs(first_exception, raised_exception)

    def test_equality(self):
        validator1 = validation.All(validation.Exists(), validation.UserWritable())
        validator2 = validation.All(validation.Exists(), validation.UserWritable())
        validator3 = validation.All(validation.Exists())
        validator4 = validation.All(validation.Exists(), validation.UserExecutable())

        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)
        self.assertNotEqual(validator1, validator3)
        self.assertNotEqual(validator1, validator4)


@access_permission_test
class TestExists(unittest.TestCase, ArgparseTester):
    def test_does_nothing_if_exists(self):
        validator = validation.Exists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Should NOT raise with existent path
            arg = tmp_dir_name
            path = pathlib.Path(arg)
            validator(path, arg)

    def test_raises_if_doesnt_exist(self):
        validator = validation.Exists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Should raise with non-existent path
            arg = f"{tmp_dir_name}/non-existent"
            path = pathlib.Path(arg)
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(path, arg)

    def test_raises_if_not_enough_permissions(self):
        validator = validation.Exists()
        inside_file = pathlib.Path("file.txt")

        def mock_stat(path, **kwargs):
            if path == inside_file:
                raise PermissionError

        with mock.patch("pathlib._normal_accessor.stat", mock_stat):
            # It would then not be possible to know if the file
            # exists. In that case, it should raise an error.
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(inside_file, str(inside_file.absolute()))

    @symlink_test
    def test_symlink_to_nonexistent(self):
        validator = validation.Exists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(tmp_dir_path / "nonexistent.txt")

            with self.assertRaises(argparse.ArgumentTypeError):
                validator(symlink, str(symlink.absolute()))

    @symlink_test
    def test_symlink_to_existent(self):
        validator = validation.Exists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            file_path = tmp_dir_path / "file.txt"
            file_path.touch()
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(file_path)

            # Should not raise any exception
            validator(symlink, str(symlink.absolute()))

    def test_equality(self):
        validator1 = validation.Exists()
        validator2 = validation.Exists()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestNotExists(unittest.TestCase, ArgparseTester):
    def test_does_nothing_if_doesnt_exist(self):
        validator = validation.NotExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Should NOT raise with non-existent path
            arg = f"{tmp_dir_name}/non-existent.txt"
            path = pathlib.Path(arg)
            validator(path, arg)

    def test_raises_if_exists(self):
        validator = validation.NotExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Should raise with existing path
            arg = tmp_dir_name
            path = pathlib.Path(arg)
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(path, arg)

    def test_raises_if_not_enough_permissions(self):
        validator = validation.NotExists()
        inside_file = pathlib.Path("non-existent.txt")

        def mock_stat(path, **kwargs):
            if path == inside_file:
                raise PermissionError

        with mock.patch("pathlib._normal_accessor.stat", mock_stat):
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(inside_file, str(inside_file.absolute()))

    @symlink_test
    def test_symlink_to_nonexistent(self):
        # Should NOT raise exception if a symlink exists at the path, but it
        # points to a non-existent file
        validator = validation.NotExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(tmp_dir_path / "nonexistent.txt")

            # Should not raise any exception
            validator(symlink, str(symlink.absolute()))

    @symlink_test
    def test_symlink_to_existent(self):
        # Should raise exception if a symlink exists at the path, but it
        # points to an existing file
        validator = validation.NotExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            file_path = tmp_dir_path / "file.txt"
            file_path.touch()
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(file_path)

            with self.assertRaises(argparse.ArgumentTypeError):
                validator(symlink, str(symlink.absolute()))

    def test_equality(self):
        validator1 = validation.NotExists()
        validator2 = validation.NotExists()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


@access_permission_test
class TestReadable(unittest.TestCase, AccessTestCase):
    def test_does_nothing_if_readable(self):
        validator = validation.UserReadable()
        self.assert_passes_on_file_with_mode(validator, stat.S_IRUSR | stat.S_IWUSR)

    def test_raises_if_not_readable(self):
        validator = validation.UserReadable()
        self.assert_fails_on_file_with_mode(validator, stat.S_IXUSR | stat.S_IWUSR)

    @symlink_test
    def test_symlink(self):
        validator = validation.UserReadable()
        self.assert_passes_on_linked_file_with_mode(validator, stat.S_IRUSR)
        self.assert_fails_on_linked_file_with_mode(validator, stat.S_IWUSR)

    def test_equality(self):
        validator1 = validation.UserReadable()
        validator2 = validation.UserReadable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


@access_permission_test
class TestWritable(unittest.TestCase, AccessTestCase):
    def test_does_nothing_if_writable(self):
        validator = validation.UserWritable()
        self.assert_passes_on_file_with_mode(validator, stat.S_IWUSR | stat.S_IXUSR)

    def test_raises_if_not_writable(self):
        validator = validation.UserWritable()
        self.assert_fails_on_file_with_mode(validator, stat.S_IRUSR | stat.S_IXUSR)

    @symlink_test
    def test_symlink(self):
        validator = validation.UserWritable()
        self.assert_passes_on_linked_file_with_mode(validator, stat.S_IWUSR)
        self.assert_fails_on_linked_file_with_mode(validator, stat.S_IRUSR)

    def test_equality(self):
        validator1 = validation.UserWritable()
        validator2 = validation.UserWritable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


@access_permission_test
class TestExecutable(unittest.TestCase, AccessTestCase):
    def test_does_nothing_if_executable(self):
        validator = validation.UserExecutable()
        self.assert_passes_on_file_with_mode(validator, stat.S_IWUSR | stat.S_IXUSR)

    def test_raises_if_not_executable(self):
        validator = validation.UserExecutable()
        self.assert_fails_on_file_with_mode(validator, stat.S_IRUSR | stat.S_IWUSR)

    @symlink_test
    def test_symlink(self):
        validator = validation.UserExecutable()
        self.assert_passes_on_linked_file_with_mode(validator, stat.S_IXUSR)
        self.assert_fails_on_linked_file_with_mode(validator, stat.S_IRUSR)

    def test_equality(self):
        validator1 = validation.UserExecutable()
        validator2 = validation.UserExecutable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestParentExists(unittest.TestCase, ArgparseTester):
    def test_doesnt_raise_if_parent_exists(self):
        validator = validation.ParentExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            path1 = pathlib.Path(tmp_dir_name) / "existing.txt"
            path2 = pathlib.Path(tmp_dir_name) / "not-existing"
            path1.touch()

            # Should NOT raise with existing parent
            validator(path1, str(path1))
            validator(path2, str(path2))

    def test_raise_if_parent_doesnt_exist(self):
        validator = validation.ParentExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            path = pathlib.Path(tmp_dir_name) / "inexistant/my_file.txt"

            # Should raise with non-existent parent
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(path, str(path))

    @access_permission_test
    def test_raises_if_cant_get_stat(self):
        """
        Test that the validator raises if we cannot get information about a directory
        to know if it exists.
        """
        validator = validation.ParentExists()

        with temp_dir_and_enter():
            dir_path = pathlib.Path("dir/sub-dir")
            dir_path.mkdir(parents=True)
            file_path = dir_path / "file.txt"

            try:
                # We remove "read" and "execute" permissions on the "dir" directory,
                # so we cannot know if "sub-dir" (the parent of the file) exists,
                # even though it actually exists
                dir_path.parent.chmod(stat.S_IWUSR)
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))
            finally:
                dir_path.parent.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def test_raises_if_no_parent(self):
        validator = validation.ParentExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            root_dir = pathlib.Path(pathlib.Path(tmp_dir_name).root)
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(root_dir, str(root_dir))

    @symlink_test
    def test_symlink_in_parents(self):
        """
        Test that symbolic links in any of the parents are resolved.
        """
        validator = validation.ParentExists()

        with temp_dir_and_enter():
            actual_dir = pathlib.Path("dir/sub-dir")
            sym_dir = pathlib.Path("sym_to_orig")
            file_path = sym_dir / "file.txt"

            actual_dir.mkdir(parents=True)
            sym_dir.symlink_to(actual_dir)

            # Should not raise any error if parent can be checked
            validator(file_path, str(file_path))

            # We change the permissions of "dir" so we can't  determine "sub-dir" exists
            actual_dir.parent.chmod(stat.S_IWUSR)

            try:
                # It would then not be possible to check the existence of the
                # test file's parent directory
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))
            finally:
                actual_dir.parent.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    @symlink_test
    def test_path_is_symlink(self):
        """
        Test that path is resolved if the file we test is a symbolic link.
        """
        validator = validation.ParentExists()

        with temp_dir_and_enter():
            actual_dir = pathlib.Path("dir/sub-dir")
            actual_file_path = actual_dir / "file.txt"
            sym_file_path = pathlib.Path("sym_to_file.txt")

            actual_dir.mkdir(parents=True)
            sym_file_path.symlink_to(actual_file_path)

            # Should not raise any error if parent can be checked
            validator(sym_file_path, str(sym_file_path))

            # We change the permissions of "dir" so we can't  determine "sub-dir" exists
            actual_dir.parent.chmod(stat.S_IWUSR)

            try:
                # It would then not be possible to check the existence of the
                # test file's parent directory
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(sym_file_path, str(sym_file_path))
            finally:
                actual_dir.parent.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def test_equality(self):
        validator1 = validation.ParentExists()
        validator2 = validation.ParentExists()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


@access_permission_test
class TestParentUserWritable(unittest.TestCase, AccessTestCase):
    def test_does_nothing_if_writable(self):
        validator = validation.ParentUserWritable()
        self.assert_passes_on_dir_with_mode(validator, stat.S_IWUSR)

    def test_raises_if_not_writable(self):
        validator = validation.ParentUserWritable()
        self.assert_fails_on_dir_with_mode(validator, stat.S_IXUSR)

    @symlink_test
    def test_symlink_in_parents(self):
        """
        Test that symbolic links in any of the parents are resolved.
        """
        validator = validation.ParentUserWritable()

        with temp_dir_and_enter():
            actual_dir = pathlib.Path("dir")
            sym_dir = pathlib.Path("sym_to_orig")
            file_path = sym_dir / "file.txt"

            actual_dir.mkdir(parents=True)
            sym_dir.symlink_to(actual_dir)

            # Should not raise any error if parent can be checked
            validator(file_path, str(file_path))

            # We remove the "write" permission of "dir"
            actual_dir.chmod(stat.S_IRUSR)

            try:
                # It would then not be possible to check the existence of the
                # test file's parent directory
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))
            finally:
                actual_dir.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    @symlink_test
    def test_path_is_symlink(self):
        """
        Test that path is resolved if the file we test is a symbolic link.
        """
        validator = validation.ParentUserWritable()

        with temp_dir_and_enter():
            actual_dir = pathlib.Path("dir")
            actual_file_path = actual_dir / "file.txt"
            sym_file_path = pathlib.Path("sym_to_file.txt")

            actual_dir.mkdir(parents=True)
            sym_file_path.symlink_to(actual_file_path)

            # Should not raise any error if parent can be checked
            validator(sym_file_path, str(sym_file_path))

            # We remove the "write" the permissions of "dir"
            actual_dir.chmod(stat.S_IRUSR)

            try:
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(sym_file_path, str(sym_file_path))
            finally:
                actual_dir.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def test_equality(self):
        validator1 = validation.ParentUserWritable()
        validator2 = validation.ParentUserWritable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestNameMatches(unittest.TestCase, PatternMatcherTestCase):
    @property
    def _matcher(self) -> Type[validation.PatternMatches]:
        return validation.NameMatches

    def test_passes_with_matching_re_pattern(self):
        posix_file_path = pathlib.PurePosixPath("path/to/my_file_123.txt")
        win_file_path = pathlib.PureWindowsPath(r"path\to\my_file_123.txt")

        patterns = (
            "^.+_[0-9]+",
            "my_file_123.txt$",
            ".txt",
        )

        self.assert_passes_with_patterns(cast(pathlib.Path, posix_file_path), patterns)
        self.assert_passes_with_patterns(cast(pathlib.Path, win_file_path), patterns)

    def test_fails_with_non_matching_re_pattern(self):
        posix_file_path = pathlib.PurePosixPath("path/to/my_file_123.txt")
        win_file_path = pathlib.PureWindowsPath(r"path\to\my_file_123.txt")

        patterns = (
            "path",
            "/my_file",
            r"\\my_file",
            "my_file_(4)+",
            "^file",
        )

        self.assert_fails_with_patterns(cast(pathlib.Path, posix_file_path), patterns)
        self.assert_fails_with_patterns(cast(pathlib.Path, win_file_path), patterns)

    def test_passes_with_matching_glob(self):
        posix_file_path = pathlib.PurePosixPath("path/to/my_file_123.txt")
        win_file_path = pathlib.PureWindowsPath(r"C:\path\to\my_file_123.txt")

        globs = (
            "*.txt",
            "my_file_123.txt",
            "my_file_12?.txt",
            "my_file_[123]*",
        )

        self.assert_passes_with_globs(cast(pathlib.Path, posix_file_path), globs)
        self.assert_passes_with_globs(cast(pathlib.Path, win_file_path), globs)

    def test_fails_with_non_matching_glob(self):
        posix_file_path = pathlib.PurePosixPath("path/to/my_file_123.txt")
        win_file_path = pathlib.PureWindowsPath(r"path\to\my_file_123.txt")
        globs = (
            "my_file",
            "/my_file*",
            r"\my_file*",
            "*.t",
        )

        self.assert_fails_with_globs(cast(pathlib.Path, posix_file_path), globs)
        self.assert_fails_with_globs(cast(pathlib.Path, win_file_path), globs)

    def test_raises_if_invalid_pattern(self):
        with self.assertRaises(ValueError):
            # Invalid RE: missing a right ")"
            validation.NameMatches(pattern="((invalid)")


class TestPathMatches(unittest.TestCase, PatternMatcherTestCase):
    @property
    def _matcher(self) -> Type[validation.PatternMatches]:
        return validation.PathMatches

    def test_passes_with_matching_re_pattern(self):
        """
        Tests validation passes with matching regular expressions.

        This test is platform dependent, so you may want to run it on both Posix and
        Windows systems.
        """
        if os.name == "nt":
            file_path = pathlib.PureWindowsPath(r"C:\home\dev\path\to\my\file_123.txt")
        else:
            file_path = pathlib.PurePosixPath("/home/dev/path/to/my/file_123.txt")

        grandparent_dir = file_path.parent.parent
        patterns = (
            "path",
            re.escape(str(grandparent_dir)),
            re.escape("path" + os.sep + "to"),
            r"^.+[\\\/][^\\\/]+_[0-9]+",
            re.escape("file_123.txt"),
            ".txt",
            r"\.txt$",
        )

        self.assert_passes_with_patterns(cast(pathlib.Path, file_path), patterns)

    def test_fails_with_non_matching_re_pattern(self):
        """
        Tests validation fails with non-matching regular expressions.

        This test is platform dependent, so you may want to run it on both Posix and
        Windows systems.
        """
        if os.name == "nt":
            file_path = pathlib.PureWindowsPath(r"C:\home\dev\path\to\my\file_123.txt")
        else:
            file_path = pathlib.PurePosixPath("/home/dev/path/to/my/file_123.txt")

        # fmt: off
        patterns = (
            re.escape("^/path"),
            re.escape(r"^\\path"),
            "^file"
        )
        # fmt: on

        self.assert_fails_with_patterns(cast(pathlib.Path, file_path), patterns)

    def test_passes_with_matching_glob(self):
        """
        Tests validation passes with matching glob expressions.

        This test is platform dependent, so you may want to run it on both Posix and
        Windows systems.
        """
        if os.name == "nt":
            file_path = pathlib.PureWindowsPath(r"C:\home\dev\path\to\my\file_123.txt")
        else:
            file_path = pathlib.PurePosixPath("/home/dev/path/to/my/file_123.txt")

        globs = (
            str(file_path.parent) + os.sep + "*.txt",
            f"*{os.sep}path{os.sep}to{os.sep}*{os.sep}*.tx?",
            "*.txt",
            f"*{os.sep}file*",
            f"*{os.sep}file_12?.txt",
            f"*{os.sep}file_[123]*",
        )

        self.assert_passes_with_globs(cast(pathlib.Path, file_path), globs)

    def test_fails_with_non_matching_glob(self):
        """
        Tests validation fails with non-matching glob patterns.

        This test is platform dependent, so you may want to run it on both Posix and
        Windows systems.
        """
        if os.name == "nt":
            file_path = pathlib.PureWindowsPath(r"C:\home\dev\path\to\my\file_123.txt")
        else:
            file_path = pathlib.PurePosixPath("/home/dev/path/to/my/file_123.txt")

        globs = (f"*{os.sep}not{os.sep}file_123.txt",)

        self.assert_fails_with_globs(cast(pathlib.Path, file_path), globs)

    def test_expands_user_dir(self):
        """If a path contains "~", it's expanded to the user's dir before validation"""
        actual_user_dir = str(pathlib.Path.home())
        glob = actual_user_dir + os.sep + "*.txt"
        matcher = validation.PathMatches(glob=glob)
        file_path = pathlib.Path("~/test.txt")

        # We make sure to move out of the user's home directory by going to the root
        cwd = pathlib.Path.cwd()
        root = cwd.anchor

        try:
            os.chdir(str(root))
            if _path_in_home_dir(pathlib.Path.cwd()):
                self.skipTest(
                    "Needed to move out of the user's home directory for this test but "
                    "couldn't."
                )
            matcher(file_path, str(file_path))
        finally:
            os.chdir(str(cwd))
