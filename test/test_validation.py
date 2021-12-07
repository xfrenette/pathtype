import argparse
import itertools
import os
import pathlib
import tempfile
import unittest
from typing import Callable, Sequence

import pathtype
import pathtype.validation as validation


def _failing_validation(*args):
    raise argparse.ArgumentTypeError("Fail")


def _passing_validation(*args):
    # Do nothing
    pass


class _AccessTestCase(unittest.TestCase):
    def assert_pass_if_has_access(self, validator: Callable,
                                  modes: Sequence[int]):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            test_dir = pathlib.Path(tmp_dir_name) / "tmp_dir"
            test_file = pathlib.Path(tmp_dir_name) / "tmp_file.txt"

            test_dir.mkdir()
            test_file.touch()

            try:
                for mode, test_obj in itertools.product(modes,
                                                        (test_dir, test_file)):
                    test_obj.chmod(mode)
                    validator(test_obj, str(test_obj.absolute()))
            finally:
                # Make sure that, no matter what, the files will be able to be
                # deleted
                test_dir.chmod(0o766)
                test_file.chmod(0o766)

    def assert_fails_if_doesnt_have_access(self, validator: Callable,
                                           modes: Sequence[int]):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            test_dir = pathlib.Path(tmp_dir_name) / "tmp_dir"
            test_file = pathlib.Path(tmp_dir_name) / "tmp_file.txt"

            test_dir.mkdir()
            test_file.touch()

            try:
                for mode, test_obj in itertools.product(modes,
                                                        (test_dir, test_file)):
                    test_obj.chmod(mode)
                    with self.assertRaises(argparse.ArgumentTypeError):
                        validator(test_obj, str(test_obj.absolute()))
            finally:
                # Make sure that, no matter what, the files will be able to be
                # deleted
                test_dir.chmod(0o766)
                test_file.chmod(0o766)

    def assert_linked_file_fails(self, validator: Callable, mode: int):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            file_path = tmp_dir_path / "file.txt"
            # File's mode doesn't have the tested access
            file_path.touch(mode=mode)

            # Create a link to the file
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(file_path)

            try:
                # Should raise an exception
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(symlink, str(symlink.absolute()))
            finally:
                # Make sure that, no matter what, the file will be able to be
                # deleted
                file_path.chmod(0o766)

    def assert_works_in_argparse(self, validator: Callable, pass_mode: int,
                                 fail_mode: int):
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            pass_file = pathlib.Path(tmp_dir_name) / "pass.txt"
            pass_file.touch(mode=pass_mode)

            fail_file = pathlib.Path(tmp_dir_name) / "fail.txt"
            fail_file.touch(mode=fail_mode)

            try:
                # When it passes, we should have the path in the args
                args = parser.parse_args(["--path", str(pass_file)])
                self.assertEqual(pass_file, args.path)

                # argparse doesn't raise an exception when validation fails, instead
                # it exits the program
                with self.assertRaises(SystemExit):
                    parser.parse_args(["--path", str(fail_file)])
            finally:
                # Make sure that, no matter what, the files will be able to be
                # deleted
                pass_file.chmod(0o766)
                fail_file.chmod(0o766)


class TestAny(unittest.TestCase):
    def test_passes_if_any(self):
        any_validator = validation.Any(_failing_validation,
                                       _passing_validation,
                                       _failing_validation)
        # Shouldn't do anything
        any_validator(pathlib.Path("tmp"), "tmp")

    def test_fails_if_none_passes(self):
        any_validator = validation.Any(_failing_validation, _failing_validation)

        with self.assertRaises(argparse.ArgumentTypeError):
            any_validator(pathlib.Path("tmp"), "tmp")

    def test_returns_last_of_supported_exceptions(self):
        """
        If a validator raises one of the exceptions supported by argparse,
        the any validator should manage it and return the last one
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
        self.assertEqual(validator1, validator2)
        self.assertNotEqual(validator1, validator3)
        self.assertNotEqual(validator1, validator4)


class TestAll(unittest.TestCase):
    def test_passes_if_all(self):
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
        self.assertEqual(validator1, validator2)
        self.assertNotEqual(validator1, validator3)
        self.assertNotEqual(validator1, validator4)


class TestExists(unittest.TestCase):
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

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # We create a directory and a file within it.
            inside_dir = pathlib.Path(f"{tmp_dir_name}/dir")
            inside_dir.mkdir()
            inside_file = inside_dir / "file.txt"
            inside_file.touch()

            # But we change the permissions so that the user cannot list the
            # directory.
            inside_dir.chmod(0o200)

            try:
                # It would then not be possible to know if the file
                # exists. In that case, it should raise an error.
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(inside_file, str(inside_file.absolute()))
            finally:
                inside_dir.chmod(0o766)

    def test_symlink_to_nonexistent(self):
        validator = validation.Exists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(tmp_dir_path / "nonexistent.txt")

            with self.assertRaises(argparse.ArgumentTypeError):
                validator(symlink, str(symlink.absolute()))

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
            with self.assertRaises(SystemExit):
                # The following line will output to STDERR something like
                # "usage: [...] error: argument --path: path exists". It's
                # all good.
                parser.parse_args(["--path", f"{tmp_dir_name}/non-existent"])

    def test_equality(self):
        validator1 = validation.Exists()
        validator2 = validation.Exists()
        self.assertEqual(validator1, validator2)


class TestNotExists(unittest.TestCase):
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

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # We create a directory and a file within it.
            inside_dir = pathlib.Path(f"{tmp_dir_name}/dir")
            inside_dir.mkdir()
            inside_file = inside_dir / "non-existent.txt"

            # But we change the permissions so that the user cannot list the
            # directory.
            inside_dir.chmod(0o600)

            try:
                # It would then not be possible to know if the file
                # exists or not. In that case, it should raise an error
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(inside_file, str(inside_file.absolute()))
            finally:
                inside_dir.chmod(0o766)

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
            with self.assertRaises(SystemExit):
                # The following line will output to STDERR something like
                # "usage: [...] error: argument --path: path exists". It's
                # all good.
                parser.parse_args(["--path", tmp_dir_name])

    def test_equality(self):
        validator1 = validation.NotExists()
        validator2 = validation.NotExists()
        self.assertEqual(validator1, validator2)


class TestReadable(_AccessTestCase):
    def test_does_nothing_if_readable(self):
        validator = validation.UserReadable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o700, 0o477)
        self.assert_pass_if_has_access(validator, modes)

    def test_raises_if_not_readable(self):
        validator = validation.UserReadable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o333, 0o077)
        self.assert_fails_if_doesnt_have_access(validator, modes)

    def test_symlink(self):
        validator = validation.UserReadable()
        self.assert_linked_file_fails(validator, 0o300)

    def test_inside_argparse(self):
        validator = validation.UserReadable()
        self.assert_works_in_argparse(validator, 0o400, 0o200)

    def test_equality(self):
        validator1 = validation.UserReadable()
        validator2 = validation.UserReadable()
        self.assertEqual(validator1, validator2)


class TestWritable(_AccessTestCase):
    def test_does_nothing_if_writable(self):
        validator = validation.UserWritable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o700, 0o277)
        self.assert_pass_if_has_access(validator, modes)

    def test_raises_if_not_writable(self):
        validator = validation.UserWritable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o533, 0o077)
        self.assert_fails_if_doesnt_have_access(validator, modes)

    def test_symlink(self):
        validator = validation.UserWritable()
        self.assert_linked_file_fails(validator, 0o500)

    def test_inside_argparse(self):
        validator = validation.UserWritable()
        self.assert_works_in_argparse(validator, 0o200, 0o500)

    def test_equality(self):
        validator1 = validation.UserWritable()
        validator2 = validation.UserWritable()
        self.assertEqual(validator1, validator2)


class TestExecutable(_AccessTestCase):
    def test_does_nothing_if_executable(self):
        validator = validation.UserExecutable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o100, 0o377)
        self.assert_pass_if_has_access(validator, modes)

    def test_raises_if_not_executable(self):
        validator = validation.UserExecutable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o633, 0o077)
        self.assert_fails_if_doesnt_have_access(validator, modes)

    def test_symlink(self):
        validator = validation.UserExecutable()
        self.assert_linked_file_fails(validator, 0o600)

    def test_inside_argparse(self):
        validator = validation.UserExecutable()
        self.assert_works_in_argparse(validator, 0o300, 0o200)

    def test_equality(self):
        validator1 = validation.UserExecutable()
        validator2 = validation.UserExecutable()
        self.assertEqual(validator1, validator2)


class TestParentExists(unittest.TestCase):
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

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # We create a directory with another directory within it.
            main_dir = pathlib.Path(f"{tmp_dir_name}/dir")
            main_dir.mkdir()
            sub_dir = main_dir / "sub-dir"
            test_file = sub_dir / "my-file.txt"

            # But we change the permissions so that the user cannot list the
            # directory
            main_dir.chmod(0o600)

            try:
                # It would then not be possible to check the existence of the
                # test file's parent directory
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(test_file, str(test_file))
            finally:
                main_dir.chmod(0o766)

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
        parser = argparse.ArgumentParser()
        validator = validation.ParentExists()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            sub_dir = pathlib.Path(tmp_dir_name) / "sub-dir"
            sub_dir.mkdir()
            # When the parent exists, we should then have the path in the
            # args
            os.chdir(tmp_dir_name)
            expected = pathlib.Path(sub_dir.name)
            args = parser.parse_args(["--path", str(expected)])
            self.assertEqual(expected, args.path)

            # Should fail if the parent doesn't exist
            # argparse doesn't raise an exception when validation fails, instead
            # it exits the program
            with self.assertRaises(SystemExit):
                # The following line will output to STDERR something like
                # "usage: [...] error: argument --path: path exists". It's
                # all good.
                parser.parse_args(["--path", "non-existent/sub-file"])

    def test_equality(self):
        validator1 = validation.ParentExists()
        validator2 = validation.ParentExists()
        self.assertEqual(validator1, validator2)


class TestParentUserWritable(_AccessTestCase):
    def test_does_nothing_if_writable(self):
        validator = validation.ParentUserWritable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o700, 0o277)

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            parent_dir = pathlib.Path(tmp_dir_name) / "parent"
            other_dir = pathlib.Path(tmp_dir_name) / "other_dir"
            test_file = pathlib.Path("../parent/file.txt")

            parent_dir.mkdir()
            other_dir.mkdir()
            os.chdir(other_dir)

            try:
                for mode in modes:
                    parent_dir.chmod(mode)
                    validator(test_file, str(test_file))
            finally:
                # Make sure that, no matter what, the files will be able to be
                # deleted
                parent_dir.chmod(0o766)

    def test_raises_if_not_writable(self):
        validator = validation.ParentUserWritable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to change ownership of the test file, and thus unable to
        # test when the user is not the owner of the file.
        modes = (0o557, 0o140)

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            parent_dir = pathlib.Path(tmp_dir_name) / "parent"
            other_dir = pathlib.Path(tmp_dir_name) / "other_dir"
            test_file = pathlib.Path("../parent/file.txt")

            parent_dir.mkdir()
            other_dir.mkdir()
            (parent_dir / test_file.name).touch()
            os.chdir(other_dir)

            try:
                for mode in modes:
                    parent_dir.chmod(mode)
                    with self.assertRaises(argparse.ArgumentTypeError):
                        validator(test_file, str(test_file))
            finally:
                # Make sure that, no matter what, the files will be able to be
                # deleted
                parent_dir.chmod(0o766)

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
        parser = argparse.ArgumentParser()
        validator = validation.ParentUserWritable()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            sub_dir = pathlib.Path(tmp_dir_name) / "sub-dir"
            test_file = pathlib.Path("sub-dir/test_file.txt")
            sub_dir.mkdir()
            # When the parent is writable, we should be able to extract the file
            os.chdir(tmp_dir_name)
            args = parser.parse_args(["--path", str(test_file)])
            self.assertEqual(test_file, args.path)

            try:
                # Should fail if the parent is not writable
                sub_dir.chmod(0o500)
                # argparse doesn't raise an exception when validation fails, instead
                # it exits the program
                with self.assertRaises(SystemExit):
                    # The following line will output to STDERR something like
                    # "usage: [...] error: argument --path: path exists". It's
                    # all good.
                    parser.parse_args(["--path", str(test_file)])
            finally:
                sub_dir.chmod(0o766)

    def test_equality(self):
        validator1 = validation.ParentUserWritable()
        validator2 = validation.ParentUserWritable()
        self.assertEqual(validator1, validator2)
