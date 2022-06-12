import argparse
import contextlib
import os
import pathlib
import re
import sys
import tempfile
import unittest
from typing import Callable, Sequence, Type
from unittest import mock

import pathtype
import pathtype.validation as validation
from .mixins import ArgparseTester


def _failing_validation(*args):
    raise argparse.ArgumentTypeError("Fail")


def _passing_validation(*args):
    # Do nothing
    pass


@contextlib.contextmanager
def _chdir(path):
    cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(cwd)


def _symlink_test(test):
    return unittest.skipIf(sys.platform.startswith("win"), "Symlink tests skipped on Windows")(test)


class _AccessTestCase(unittest.TestCase, ArgparseTester):
    def assert_pass_if_has_access(self, validator: Callable, mode_to_test: int):
        test_file = pathlib.Path("tmp_file.txt")

        def mock_access(path, mode, *args, **kwargs):
            if path == test_file and (mode & mode_to_test):
                return True
            return False

        with mock.patch("os.access", mock_access):
            validator(test_file, str(test_file.absolute()))

    def assert_fails_if_doesnt_have_access(self, validator: Callable, mode_to_test: int):
        test_file = pathlib.Path("tmp_file.txt")

        def mock_access(path, mode, *args, **kwargs):
            if path == test_file and (mode & mode_to_test):
                return True
            return False

        with mock.patch("os.access", mock_access):
            validator(test_file, str(test_file))

    @contextlib.contextmanager
    def mock_file_mode(self, test_file: pathlib.Path, mode_to_mock: int):
        orig_os_access = os.access

        def mock_access(path, mode, *args, **kwargs):
            if path.resolve().absolute() == test_file.resolve().absolute():
                return mode & mode_to_mock
            return orig_os_access(path, mode, *args, **kwargs)

        with mock.patch("os.access", mock_access):
            yield

    @contextlib.contextmanager
    def file_stat_error(self, test_file: pathlib.Path):
        orig_stat = os.stat

        def mock_stat(path, *args, **kwargs):
            if path == test_file:
                raise PermissionError
            return orig_stat(path, *args, **kwargs)

        with mock.patch("pathlib._normal_accessor.stat", mock_stat):
            yield

    def assert_linked_file_access_fails(self, validator: Callable, mode_to_test: int):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            file_path = tmp_dir_path / "file.txt"

            # Create a link to the file
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(file_path)

            orig_os_access = os.access

            def mock_access(path, mode, *args, **kwargs):
                if path == file_path and (mode & mode_to_test):
                    return True
                return orig_os_access(path, mode, *args, **kwargs)

            with mock.patch("os.access", mock_access):
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(symlink, str(symlink.absolute()))

    def assert_works_in_argparse(self, validator: Callable, pass_with_mode: int, fail_with_mode: int):
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))
        pass_file = pathlib.Path("pass.txt")
        fail_file = pathlib.Path("fail.txt")

        with self.mock_file_mode(pass_file, pass_with_mode):
            # When it passes, we should have the path in the args
            args = parser.parse_args(["--path", str(pass_file)])
            self.assertEqual(pass_file, args.path)

        with self.mock_file_mode(fail_file, fail_with_mode):
            with self.assert_argparse_error(parser):
                parser.parse_args(["--path", str(fail_file)])


class TestAny(unittest.TestCase):
    def test_passes_if_any_passes(self):
        any_validator = validation.Any(_failing_validation,
                                       _passing_validation,
                                       _failing_validation)
        # Shouldn't do anything
        any_validator(pathlib.Path("tmp"), "tmp")

    def test_fails_if_none_pass(self):
        any_validator = validation.Any(_failing_validation, _failing_validation)

        with self.assertRaises(argparse.ArgumentTypeError):
            any_validator(pathlib.Path("tmp"), "tmp")

    def test_returns_last_of_supported_exceptions(self):
        """
        If a validator raises one of the exceptions supported by argparse,
        the "any" validator should manage it and return the last one.
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
        If a validator raise any other exception not supported by argparse, it
        should be raised immediately
        """
        last_exception = Exception("--Test exception--")

        def failing_validator(*args):
            raise last_exception

        any_validator = validation.Any(_failing_validation, failing_validator,
                                       _passing_validation)

        with self.assertRaises(type(last_exception)) as raised_exception:
            any_validator(pathlib.Path("tmp"), "tmp")
            self.assertIs(last_exception, raised_exception)

    def test_equality(self):
        validator1 = validation.Any(validation.Exists(),
                                    validation.UserWritable())
        validator2 = validation.Any(validation.Exists(),
                                    validation.UserWritable())
        validator3 = validation.Any(validation.Exists())
        validator4 = validation.Any(validation.Exists(),
                                    validation.UserExecutable())
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)
        self.assertNotEqual(validator1, validator3)
        self.assertNotEqual(validator1, validator4)


class TestAll(unittest.TestCase):
    def test_passes_if_all_pass(self):
        all_validator = validation.All(_passing_validation,
                                       _passing_validation,
                                       _passing_validation)
        # Shouldn't do anything
        all_validator(pathlib.Path("tmp"), "tmp")

    def test_fails_if_any_fails(self):
        all_validator = validation.All(_passing_validation,
                                       _passing_validation,
                                       _failing_validation,
                                       _passing_validation)

        with self.assertRaises(argparse.ArgumentTypeError):
            all_validator(pathlib.Path("tmp"), "tmp")

    def test_returns_first_exceptions(self):
        for ExceptionType in (TypeError, Exception):
            first_exception = ExceptionType("--Test exception--")

            def first_validator(*args):
                raise first_exception

            all_validator = validation.All(_passing_validation,
                                           first_validator,
                                           _failing_validation)

            with self.assertRaises(ExceptionType) as raised_exception:
                all_validator(pathlib.Path("tmp"), "tmp")
                self.assertIs(first_exception, raised_exception)

    def test_equality(self):
        validator1 = validation.All(validation.Exists(),
                                    validation.UserWritable())
        validator2 = validation.All(validation.Exists(),
                                    validation.UserWritable())
        validator3 = validation.All(validation.Exists())
        validator4 = validation.All(validation.Exists(),
                                    validation.UserExecutable())
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)
        self.assertNotEqual(validator1, validator3)
        self.assertNotEqual(validator1, validator4)


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

        def mock_stat(path):
            if path == inside_file:
                raise PermissionError

        with mock.patch("pathlib._normal_accessor.stat", mock_stat):
            # It would then not be possible to know if the file
            # exists. In that case, it should raise an error.
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(inside_file, str(inside_file.absolute()))

    @_symlink_test
    def test_symlink_to_nonexistent(self):
        validator = validation.Exists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(tmp_dir_path / "nonexistent.txt")

            with self.assertRaises(argparse.ArgumentTypeError):
                validator(symlink, str(symlink.absolute()))

    @_symlink_test
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

    def test_inside_argparse(self):
        parser = argparse.ArgumentParser()
        validator = validation.Exists()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # When the path exists, we should then have it in the args
            expected_path = pathlib.Path(tmp_dir_name)
            args = parser.parse_args(["--path", tmp_dir_name])
            self.assertEqual(expected_path, args.path)

            # argparse doesn't raise an exception when validation fails, instead
            # it exits the program
            with self.assert_argparse_error(parser):
                # The following line will output to STDERR something like
                # "usage: [...] error: argument --path: path exists". It's
                # all good.
                parser.parse_args(["--path", f"{tmp_dir_name}/non-existent"])

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

        def mock_stat(path):
            if path == inside_file:
                raise PermissionError

        with mock.patch("pathlib._normal_accessor.stat", mock_stat):
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(inside_file, str(inside_file.absolute()))

    @_symlink_test
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

    @_symlink_test
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

    def test_inside_argparse(self):
        parser = argparse.ArgumentParser()
        validator = validation.NotExists()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # When the path doesn't exist, we should then have it in the args
            expected_path = pathlib.Path(f"{tmp_dir_name}/non-existent")
            args = parser.parse_args(["--path", str(expected_path)])
            self.assertEqual(expected_path, args.path)

            # argparse doesn't raise an exception when validation fails, instead
            # it exits the program
            with self.assert_argparse_error(parser):
                # The following line will output to STDERR something like
                # "usage: [...] error: argument --path: path exists". It's
                # all good.
                parser.parse_args(["--path", tmp_dir_name])

    def test_equality(self):
        validator1 = validation.NotExists()
        validator2 = validation.NotExists()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestReadable(_AccessTestCase):
    def test_does_nothing_if_readable(self):
        validator = validation.UserReadable()
        test_file = pathlib.Path("test.txt")

        with self.mock_file_mode(test_file, os.R_OK | os.W_OK):
            validator(test_file, str(test_file))

    def test_raises_if_not_readable(self):
        validator = validation.UserReadable()
        test_file = pathlib.Path("test.txt")

        with self.mock_file_mode(test_file, os.W_OK | os.X_OK):
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(test_file, str(test_file))

    @_symlink_test
    def test_symlink(self):
        validator = validation.UserReadable()
        self.assert_linked_file_access_fails(validator, os.W_OK)

    def test_inside_argparse(self):
        validator = validation.UserReadable()
        self.assert_works_in_argparse(validator, os.R_OK, os.W_OK)

    def test_equality(self):
        validator1 = validation.UserReadable()
        validator2 = validation.UserReadable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestWritable(_AccessTestCase):
    def test_does_nothing_if_writable(self):
        validator = validation.UserWritable()
        test_file = pathlib.Path("test.txt")

        with self.mock_file_mode(test_file, os.W_OK | os.X_OK):
            validator(test_file, str(test_file))

    def test_raises_if_not_writable(self):
        validator = validation.UserWritable()
        test_file = pathlib.Path("test.txt")

        with self.mock_file_mode(test_file, os.R_OK | os.X_OK):
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(test_file, str(test_file))

    @_symlink_test
    def test_symlink(self):
        validator = validation.UserWritable()
        self.assert_linked_file_access_fails(validator, os.X_OK)

    def test_inside_argparse(self):
        validator = validation.UserWritable()
        self.assert_works_in_argparse(validator, os.W_OK, os.X_OK)

    def test_equality(self):
        validator1 = validation.UserWritable()
        validator2 = validation.UserWritable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestExecutable(_AccessTestCase):
    def test_does_nothing_if_executable(self):
        validator = validation.UserExecutable()
        test_file = pathlib.Path("test.txt")

        with self.mock_file_mode(test_file, os.R_OK | os.X_OK):
            validator(test_file, str(test_file))

    def test_raises_if_not_executable(self):
        validator = validation.UserExecutable()
        test_file = pathlib.Path("test.txt")

        with self.mock_file_mode(test_file, os.R_OK | os.W_OK):
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(test_file, str(test_file))

    @_symlink_test
    def test_symlink(self):
        validator = validation.UserExecutable()
        self.assert_linked_file_access_fails(validator, os.R_OK)

    def test_inside_argparse(self):
        validator = validation.UserExecutable()
        self.assert_works_in_argparse(validator, os.X_OK, os.R_OK)

    def test_equality(self):
        validator1 = validation.UserExecutable()
        validator2 = validation.UserExecutable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestParentExists(_AccessTestCase):
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

    def test_raises_if_not_enough_permissions(self):
        validator = validation.ParentExists()
        test_file = pathlib.Path("sub-dir/my-file.txt")

        with self.file_stat_error(test_file.parent):
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(test_file, str(test_file))

    @_symlink_test
    def test_symlink_in_parents(self):
        """
        Test that symbolic links in the path are resolved when determining the
        parent
        """
        validator = validation.ParentExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Original directory containing the file.
            orig_dir = pathlib.Path(tmp_dir_name) / "unreadable/orig"
            # Symbolic link to orig dir
            sym_dir = pathlib.Path(tmp_dir_name) / "sym_to_orig"
            test_file = pathlib.Path("my_file.txt")

            orig_dir.mkdir(parents=True)
            sym_dir.symlink_to(orig_dir)

            os.chdir(sym_dir)

            # Should not raise any error if parent can be checked
            validator(test_file, str(test_file))

            # We change the permissions of the parent of the orig_dir so we
            # can't determine if it exists
            orig_dir.parent.chmod(0o600)

            try:
                # It would then not be possible to check the existence of the
                # test file's parent directory
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(test_file, str(test_file))
            finally:
                orig_dir.parent.chmod(0o766)

    @_symlink_test
    def test_path_is_symlink(self):
        """
        Test that symbolic links in the path are resolved when determining the
        parent
        """
        validator = validation.ParentExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Original directory containing the file.
            orig_dir = pathlib.Path(tmp_dir_name) / "unreadable/orig"
            orig_file = orig_dir / "my_file.txt"
            # Symbolic link to orig file
            sym_file = pathlib.Path(tmp_dir_name) / "sym_to_my_file.txt"
            test_file = pathlib.Path(sym_file.name)

            orig_dir.mkdir(parents=True)
            orig_file.touch()
            sym_file.symlink_to(orig_file)

            os.chdir(tmp_dir_name)

            # Should not raise any error if parent can be checked
            validator(test_file, str(test_file))

            # We change the permissions of the parent of the orig_file parent
            # directory's parent so we can't determine if the parent of
            # orig_file exists
            orig_dir.parent.chmod(0o600)

            try:
                # It would then not be possible to check the existence of the
                # test file's parent directory
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(test_file, str(test_file))
            finally:
                orig_dir.parent.chmod(0o766)

    def test_raises_if_no_parent(self):
        validator = validation.ParentExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            root_dir = pathlib.Path(pathlib.Path(tmp_dir_name).root)
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(root_dir, str(root_dir))

    def test_inside_argparse(self):
        validator = validation.ParentExists()
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))
        cwd = os.getcwd()

        tmp_dir = tempfile.TemporaryDirectory()
        tmp_dir_name = tmp_dir.name
        try:
            os.chdir(tmp_dir_name)

            sub_dir = pathlib.Path("sub-dir")
            sub_dir.mkdir()

            args = parser.parse_args(["--path", str(sub_dir)])
            self.assertEqual(sub_dir, args.path)

            with self.assertRaises(SystemExit):
                parser.parse_args(["--path", "non-existent/sub-file"])
        finally:
            os.chdir(cwd)
            tmp_dir.cleanup()

    def test_equality(self):
        validator1 = validation.ParentExists()
        validator2 = validation.ParentExists()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class TestParentUserWritable(_AccessTestCase, ArgparseTester):
    def test_does_nothing_if_writable(self):
        validator = validation.ParentUserWritable()
        parent_dir = pathlib.Path("parent")
        test_file = parent_dir / "test.txt"

        with self.mock_file_mode(parent_dir, os.W_OK | os.X_OK):
            validator(test_file, str(test_file))

    def test_raises_if_not_writable(self):
        validator = validation.ParentUserWritable()
        parent_dir = pathlib.Path("parent")
        test_file = parent_dir / "test.txt"

        with self.mock_file_mode(parent_dir, os.R_OK | os.X_OK):
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(test_file, str(test_file))

    @_symlink_test
    def test_symlink_in_parents(self):
        """
        Test that symbolic links in the path are resolved when determining the
        parent
        """
        validator = validation.ParentUserWritable()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Original directory containing the file.
            orig_dir = pathlib.Path(tmp_dir_name) / "directory/subdir"
            # Symbolic link to orig dir
            sym_dir = pathlib.Path(tmp_dir_name) / "sym_to_orig"
            test_file = pathlib.Path("./sym_to_orig/test/../my_file.txt")

            orig_dir.mkdir(parents=True)
            sym_dir.symlink_to(orig_dir)

            os.chdir(tmp_dir_name)

            # Should not raise any error if parent is writable
            validator(test_file, str(test_file))

            # We remove write permission (for user) on orig_dir
            orig_dir.chmod(0o557)

            try:
                # Validation should then fail
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(test_file, str(test_file))
            finally:
                orig_dir.chmod(0o766)

    @_symlink_test
    def test_path_is_symlink(self):
        """
        Test that symbolic links in the path are resolved when determining the
        parent
        """
        validator = validation.ParentUserWritable()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Original directory containing the file.
            orig_dir = pathlib.Path(tmp_dir_name) / "directory/subdir"
            orig_file = orig_dir / "my_file.txt"
            # Symbolic link to orig file
            sym_file = pathlib.Path(tmp_dir_name) / "sym_to_my_file.txt"
            test_file = pathlib.Path(f"test/../{sym_file.name}")

            orig_dir.mkdir(parents=True)
            orig_file.touch()
            sym_file.symlink_to(orig_file)

            os.chdir(tmp_dir_name)

            # Should not raise any error if parent is writable
            validator(test_file, str(test_file))

            # We remove user's write permission on the orig_dir
            orig_dir.chmod(0o547)

            try:
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(test_file, str(test_file))
            finally:
                orig_dir.chmod(0o766)

    def test_inside_argparse(self):
        validator = validation.ParentUserWritable()
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))
        cwd = os.getcwd()

        tmp_dir = tempfile.TemporaryDirectory()
        tmp_dir_name = tmp_dir.name

        try:
            os.chdir(tmp_dir_name)

            # Since we create the sub-dir in the temp directory, it will be writable by the user
            sub_dir = pathlib.Path("sub-dir")
            test_file = sub_dir / "test_file.txt"
            sub_dir.mkdir()
            # When the parent is writable, we should be able to extract the file
            args = parser.parse_args(["--path", str(test_file)])
            self.assertEqual(test_file, args.path)

            with self.mock_file_mode(sub_dir, os.R_OK | os.X_OK):
                with self.assertRaises(SystemExit):
                    parser.parse_args(["--path", str(test_file)])
        finally:
            os.chdir(cwd)
            tmp_dir.cleanup()

    def test_equality(self):
        validator1 = validation.ParentUserWritable()
        validator2 = validation.ParentUserWritable()
        self.assertEqual(validator1, validator1)
        self.assertEqual(validator1, validator2)


class _PatternMatcherTestCase(unittest.TestCase):
    @property
    def _matcher(self) -> Type[validation.PatternMatches]:
        raise NotImplemented

    def _test_re_patterns(self, file_path: pathlib.Path,
                          valid_patterns: Sequence[str],
                          invalid_patterns: Sequence[str]):
        for valid_pattern in valid_patterns:
            with self.subTest(type="valid", pattern=valid_pattern):
                # Raw string
                validator = self._matcher(valid_pattern)
                # Should not raise any error
                validator(file_path, str(file_path))

                # Compiled regular expression
                validator = self._matcher(re.compile(valid_pattern))
                # Should not raise any error
                validator(file_path, str(file_path))

        for invalid_pattern in invalid_patterns:
            with self.subTest(type="invalid", pattern=invalid_pattern):
                # Raw string
                validator = self._matcher(invalid_pattern)
                # Should raise an error
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))

                # Compiled regular expression
                validator = self._matcher(re.compile(invalid_pattern))
                # Should raise an error
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))

    def _test_glob_patterns(self, file_path: pathlib.Path,
                            valid_globs: Sequence[str],
                            invalid_globs: Sequence[str]):

        for valid_glob in valid_globs:
            with self.subTest(type="valid", pattern=valid_glob):
                # Raw string
                validator = self._matcher(glob=valid_glob)
                # Should not raise any error
                validator(file_path, str(file_path))

        for invalid_glob in invalid_globs:
            with self.subTest(type="invalid", pattern=invalid_glob):
                # Raw string
                validator = self._matcher(glob=invalid_glob)
                # Should raise an error
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))

    def test_raises_if_no_pattern_and_no_glob(self):
        with self.assertRaises(ValueError):
            self._matcher()

    def test_raises_if_both_pattern_and_glob(self):
        with self.assertRaises(ValueError):
            self._matcher("pattern", "glob")

    def test_equality(self):
        # Test with string pattern

        validator_base = self._matcher("test")
        validator_equal = self._matcher("test")
        validator_ne = self._matcher("test2")

        self.assertEqual(validator_base, validator_base)
        self.assertEqual(validator_base, validator_equal)
        self.assertNotEqual(validator_base, validator_ne)

        # Test with compiled pattern.
        #
        # Note: When creating a new pattern instance using the same pattern
        # string as another pattern instance, Python will generally reuse the
        # same instance instead of creating a new instance (see creation of
        # `pattern1` and `pattern2` below). It thus prevents us to create
        # different instances of equal patterns to then compare them. To
        # prevent the caching, we use re.DEBUG. The debug mode has a side
        # effect of outputting compiled patterns on stdout after compilation.
        # To avoid those messages, we temporarily catch and dismiss any
        # output to stdout.
        with contextlib.redirect_stdout(None):
            pattern1 = re.compile("test", re.DEBUG)
            pattern2 = re.compile("test", re.DEBUG)
        pattern3 = re.compile("test", re.IGNORECASE)
        validator_base = self._matcher(pattern1)
        validator_equal = self._matcher(pattern2)
        validator_ne = self._matcher(pattern3)

        self.assertEqual(validator_base, validator_base)
        self.assertEqual(validator_base, validator_equal)
        self.assertNotEqual(validator_base, validator_ne)

        # Test with glob pattern

        validator_base = self._matcher(glob="*.test")
        validator_equal = self._matcher(glob="*.test")
        validator_ne = self._matcher(glob="*.other")

        self.assertEqual(validator_base, validator_base)
        self.assertEqual(validator_base, validator_equal)
        self.assertNotEqual(validator_base, validator_ne)


class TestNameMatches(_PatternMatcherTestCase):

    @property
    def _matcher(self) -> Type[validation.PatternMatches]:
        return validation.NameMatches

    def test_with_re_pattern(self):
        file_path = pathlib.Path("path/to/my_file_123.txt")

        # Validation should pass when using patterns in the following list
        valid_patterns = (
            "^.+_[0-9]+",
            "my_file_123.txt",
            ".txt",
        )

        # Validation shouldn't pass when using patterns in the following list
        invalid_patterns = (
            "path",
            "/my_file"
        )

        self._test_re_patterns(file_path, valid_patterns, invalid_patterns)

    def test_with_glob(self):
        file_path = pathlib.Path("path/to/my_file_123.txt")

        # Validation should pass when using globs in the following list
        valid_globs = (
            "*.txt",
            "my_file_123.txt",
            "my_file_12?.txt",
            "my_file_[123]*",
        )

        # Validation shouldn't pass when using globs in the following list
        invalid_globs = (
            "my_file",
            "/my_file*",
            "*.t",
        )

        self._test_glob_patterns(file_path, valid_globs, invalid_globs)

    def test_raises_if_invalid_pattern(self):
        with self.assertRaises(ValueError):
            # Invalid RE: missing a right ")"
            validation.NameMatches("((invalid)")


class TestPathMatches(_PatternMatcherTestCase):

    @property
    def _matcher(self) -> Type[validation.PatternMatches]:
        return validation.PathMatches

    def test_with_re_pattern(self):
        # Should work even if the path doesn't exist (no error raised)
        validator = validation.PathMatches("test")
        path = pathlib.Path("../non-existent/directory/to/test/my_file.txt")
        validator(path, str(path))
        # Windows style
        path = pathlib.Path(r"..\non-existent\directory\to\test\my_file.txt")
        validator(path, str(path))

        file_path = pathlib.Path("path/to/my_file_123.txt")
        with tempfile.TemporaryDirectory() as tmp_dir, _chdir(tmp_dir):
            tmp_dir_path = pathlib.Path(tmp_dir)

            # Validation should pass when using patterns in the following list
            valid_patterns = (
                tmp_dir_path.name,
                str(tmp_dir_path.absolute()),
                tmp_dir_path.name + "/path",
                "^.+/[^/]+_[0-9]+",
                "my_file_123.txt",
                ".txt",
                ".txt$"
            )

            # Validation shouldn't pass when using patterns in the following list
            invalid_patterns = (
                "^/path",
                "^my_file"
            )
            self._test_re_patterns(file_path, valid_patterns, invalid_patterns)

            # Test with up-level references
            validator = validation.PathMatches("dir1/dir3")
            path = pathlib.Path("dir1/dir2/../dir3/file")
            validator(path, str(path))

    def test_with_glob(self):
        # Should work even if the path doesn't exist (no error raised)
        validator = validation.PathMatches(glob="*[\\/]to[\\/]*[\\/]*.txt")
        test_path = "../non-existent/directory/to/test/my_file.txt"
        # Linux
        path = pathlib.PurePosixPath(test_path)
        validator(path, str(path))
        # Windows
        path = pathlib.PureWindowsPath(test_path.replace("/", "\\"))
        validator(path, str(path))

        file_path = pathlib.Path("path/to/my_file_123.txt")
        with tempfile.TemporaryDirectory() as tmp_dir, _chdir(tmp_dir):
            tmp_dir_path = pathlib.Path(tmp_dir)

            # Validation should pass when using globs in the following list
            valid_globs = (
                tmp_dir + "/*.txt",
                f"*/{tmp_dir_path.name}/path/*/*.tx?",
                "*.txt",
                "*/my_file*",
                "*/my_file_12?.txt",
                "*/my_file_[123]*",
                r"*\my_file_[123]*",  # Windows style
            )

            # Validation shouldn't pass when using globs in the following list
            invalid_globs = (
                "*/not/my_file_123.txt",
                r"*\not\my_file_123.txt",  # Windows style
            )

            self._test_glob_patterns(file_path, valid_globs, invalid_globs)

            # Test with up-level references
            validator = validation.PathMatches("dir1/dir3")
            path = pathlib.Path("dir1/dir2/../dir3/file")
            validator(path, str(path))
            # Same, but Windows style Path
            path = pathlib.PureWindowsPath("dir1\\dir2\\..\\dir3\\file")
            validator(path, str(path))
