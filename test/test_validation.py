import argparse
import pathlib
import tempfile
import unittest

import pathtype
import pathtype.validation as validation


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
            inside_dir.chmod(0o666)

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
