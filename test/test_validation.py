import argparse
import itertools
import pathlib
import tempfile
import unittest
from typing import Callable, Sequence

import pathtype
import pathtype.validation as validation


class _AccessTestCase(unittest.TestCase):
    def assert_pass_if_has_access(self, validator: Callable,
                                  modes: Sequence[int]):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            test_dir = pathlib.Path(tmp_dir_name) / "tmp_dir"
            test_file = pathlib.Path(tmp_dir_name) / "tmp_file.txt"

            test_dir.mkdir()
            test_file.touch()

            try:
                for mode, test_obj in itertools.product(modes, (test_dir, test_file)):
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


class TestPathExists(unittest.TestCase):
    def test_does_nothing_if_exists(self):
        validator = validation.PathExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Should NOT raise with existent path
            arg = tmp_dir_name
            path = pathlib.Path(arg)
            validator(path, arg)

    def test_raises_if_doesnt_exist(self):
        validator = validation.PathExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # Should raise with non-existent path
            arg = f"{tmp_dir_name}/non-existent"
            path = pathlib.Path(arg)
            with self.assertRaises(argparse.ArgumentTypeError):
                validator(path, arg)

    def test_raises_if_not_enough_permissions(self):
        validator = validation.PathExists()

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
                # exists. In that case, it should be considered that the file
                # doesn't exist
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(inside_file, str(inside_file.absolute()))
            finally:
                inside_dir.chmod(0o766)

    def test_symlink_to_nonexistent(self):
        validator = validation.PathExists()

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = pathlib.Path(tmp_dir_name)
            symlink = tmp_dir_path / "link"
            symlink.symlink_to(tmp_dir_path / "nonexistent.txt")

            with self.assertRaises(argparse.ArgumentTypeError):
                validator(symlink, str(symlink.absolute()))

    def test_symlink_to_existent(self):
        validator = validation.PathExists()

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
        validator = validation.PathExists()
        parser.add_argument("--path", type=pathtype.Path(validator=validator))

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # When the path exists, we should then have it in the args
            expected_path = pathlib.Path(tmp_dir_name)
            args = parser.parse_args(["--path", tmp_dir_name])
            self.assertEqual(expected_path, args.path)

            # argparse doesn't raise an exception when validation fails, instead
            # it exits the program
            with self.assertRaises(SystemExit):
                parser.parse_args(["--path", f"{tmp_dir_name}/non-existent"])


class TestReadable(_AccessTestCase):
    def test_does_nothing_if_readable(self):
        validator = validation.UserReadable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to test when the user is not the owner of the file.
        modes = (0o700, 0o477)
        self.assert_pass_if_has_access(validator, modes)

    def test_raises_if_not_readable(self):
        validator = validation.UserReadable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to test when the user is not the owner of the file.
        modes = (0o333, 0o077)
        self.assert_fails_if_doesnt_have_access(validator, modes)

    def test_symlink(self):
        validator = validation.UserReadable()
        self.assert_linked_file_fails(validator, 0o300)

    def test_inside_argparse(self):
        validator = validation.UserReadable()
        self.assert_works_in_argparse(validator, 0o400, 0o200)


class TestWritable(_AccessTestCase):
    def test_does_nothing_if_writable(self):
        validator = validation.UserWritable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to test when the user is not the owner of the file.
        modes = (0o700, 0o277)
        self.assert_pass_if_has_access(validator, modes)

    def test_raises_if_not_writable(self):
        validator = validation.UserWritable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to test when the user is not the owner of the file.
        modes = (0o533, 0o077)
        self.assert_fails_if_doesnt_have_access(validator, modes)

    def test_symlink(self):
        validator = validation.UserWritable()
        self.assert_linked_file_fails(validator, 0o500)

    def test_inside_argparse(self):
        validator = validation.UserWritable()
        self.assert_works_in_argparse(validator, 0o200, 0o500)


class TestExecutable(_AccessTestCase):
    def test_does_nothing_if_executable(self):
        validator = validation.UserExecutable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to test when the user is not the owner of the file.
        modes = (0o100, 0o377)
        self.assert_pass_if_has_access(validator, modes)

    def test_raises_if_not_executable(self):
        validator = validation.UserExecutable()
        # Note: we test by creating temporary files. Because of that, we are
        # not able to test when the user is not the owner of the file.
        modes = (0o633, 0o077)
        self.assert_fails_if_doesnt_have_access(validator, modes)

    def test_symlink(self):
        validator = validation.UserExecutable()
        self.assert_linked_file_fails(validator, 0o600)

    def test_inside_argparse(self):
        validator = validation.UserExecutable()
        self.assert_works_in_argparse(validator, 0o300, 0o200)
