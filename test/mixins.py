"""Mixins to be used by unit test classes"""

import argparse
import contextlib
import pathlib
import re
import stat
from typing import Callable, Iterator, Optional, Type
from unittest.mock import Mock, patch

import pathtype.validation as validation
from utils import temp_dir_and_enter


class _ArgparseValidationError(Exception):
    pass


class ArgparseTester:
    """
    Mixin for test case classes that validate the integration in the argparser.

    A class that uses this mixin must inherit from unittest.TestCase.
    """

    @contextlib.contextmanager
    def assert_argument_parsing_fails(
            self,
            parser: argparse.ArgumentParser,
            msg: Optional[str] = None,
    ):
        """
        Validate that code inside the context manager triggers an argument parsing
        error.

        `parser` is the instance of ArgumentParser that must trigger a parsing error.
        If the context manager ends and the `parser` didn't generate a parsing error,
        an AssertionError is raised.

        The reason for this context manager is because, as is, it's difficult to know
        when an ArgumentParser fails argument parsing. When parsing fails,
        the ArgumentParser prints a message and exits the program, effectively
        stopping the running test. By using this context manager, the parsing error
        will be catched and the parser won't end the program. It will also prevent
        the parser to output the error message.

        Example
        >>> parser = argparse.ArgumentParser()
        >>> parser.add_argument("--valid")
        >>> with self.assert_argument_parsing_fails(parser):
        >>>     parser.parse_args(["--invalid"])
        >>>     # The following line won't be executed since the previous
        >>>     # parsing triggered an error which exited the context manager.
        >>>     print("Never reached")

        :param parser: Argument parser to test
        :param msg: Message to show on failure (i.e. the parser didn't trigger an error)
        """
        msg = msg or "Expected the parser to fail"

        def error(*args, **kwargs):
            raise _ArgparseValidationError

        mock_error: Optional[Mock] = None
        try:
            with patch.object(parser, "error") as _mock_error:
                _mock_error.side_effect = error
                mock_error = _mock_error
                yield
        except _ArgparseValidationError:
            pass
        finally:
            if mock_error.call_count == 0:
                # noinspection PyUnresolvedReferences
                self.fail(msg)


# noinspection PyUnresolvedReferences
class AccessTestCase(ArgparseTester):
    """
    Mixin that offers methods to test a validator on files with specific access
    permissions.

    This mixin is to be used on classes that inherit from unittest.TestCase and that
    test a validator.
    """

    def assert_passes_on_file_with_mode(self, validator: Callable, mode_to_test: int):
        """
        Assert that the `validator` doesn't fail when used on a file with permission
        set `mode_to_test`.
        """
        with temp_dir_and_enter():
            test_file = pathlib.Path("file.txt")
            test_file.touch(mode=mode_to_test)

            try:
                validator(test_file, str(test_file.absolute()))
            finally:
                test_file.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def assert_fails_on_file_with_mode(self, validator: Callable, mode_to_test: int):
        """
        Assert that the `validator` raises an argparse.ArgumentTypeError when used on
        a file with permission set `mode_to_test`.
        """
        with temp_dir_and_enter():
            test_file = pathlib.Path("file.txt")
            test_file.touch(mode=mode_to_test)

            try:
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(test_file, str(test_file))
            finally:
                test_file.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def assert_passes_on_dir_with_mode(self, validator: Callable, mode_to_test: int):
        """
        Assert that the `validator` doesn't fail when used on a file whose parent
        directory has permission set `mode_to_test`.
        """
        with temp_dir_and_enter():
            parent_dir = pathlib.Path("parent")
            parent_dir.mkdir()
            test_file = parent_dir / "tmp_file.txt"
            test_file.touch()
            parent_dir.chmod(mode_to_test)

            try:
                validator(test_file, str(test_file.absolute()))
            finally:
                parent_dir.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def assert_fails_on_dir_with_mode(self, validator: Callable, mode_to_test: int):
        """
        Assert that the `validator` raises an argparse.ArgumentTypeError when used on
        a file whose parent directory has the permission set `mode_to_test`.
        """
        with temp_dir_and_enter():
            parent_dir = pathlib.Path("parent")
            parent_dir.mkdir()
            test_file = parent_dir / "tmp_file.txt"
            test_file.touch()
            parent_dir.chmod(mode_to_test)

            try:
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(test_file, str(test_file))
            finally:
                parent_dir.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def assert_passes_on_linked_file_with_mode(
            self,
            validator: Callable,
            linked_file_mode: int
    ):
        """
        Assert that the `validator` doesn't fail when used on a link whose linked file
        has permission set `linked_file_mode`.
        """
        with temp_dir_and_enter():
            test_file = pathlib.Path("file.txt")
            test_file.touch(mode=linked_file_mode)
            link_file = pathlib.Path("link.txt")
            link_file.symlink_to(test_file)

            try:
                validator(link_file, str(link_file.absolute()))
            finally:
                test_file.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    def assert_fails_on_linked_file_with_mode(
            self,
            validator: Callable,
            linked_file_mode: int
    ):
        """
        Assert that the `validator` fails when used on a link whose linked file
        has permission set `linked_file_mode`.
        """
        with temp_dir_and_enter():
            test_file = pathlib.Path("file.txt")
            test_file.touch(mode=linked_file_mode)
            link_file = pathlib.Path("link.txt")
            link_file.symlink_to(test_file)

            try:
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(link_file, str(link_file.absolute()))
            finally:
                test_file.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


# noinspection PyUnresolvedReferences
class PatternMatcherTestCase:
    """
    Mixin defining tests for validators of type "pattern match".

    This mixin is to be used on classes that inherit from unittest.TestCase and that
    test a validator.
    """

    @property
    def _matcher(self) -> Type[validation.PatternMatches]:
        """
        Validation class, inheriting from `validation.PatternMatches`, to test
        """
        raise NotImplemented

    def assert_passes_with_patterns(
            self,
            file_path: pathlib.PurePath,
            patterns: Iterator[str]
    ):
        """
        Assert that a validator initialized with any of the `patterns` doesn't fail
        when executed on `file_path`.

        :param file_path: File path on which to test the validators
        :param patterns: Patterns used to initialize validators
        """
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                # Raw string
                validator = self._matcher(pattern)
                # Should not raise any error
                validator(file_path, str(file_path))

                # Compiled regular expression
                validator = self._matcher(re.compile(pattern))
                # Should not raise any error
                validator(file_path, str(file_path))

    def assert_fails_with_patterns(
            self,
            file_path: pathlib.PurePath,
            patterns: Iterator[str]
    ):
        """
        Assert that a validator initialized with any of the `patterns` fails when
        executed on `file_path`.

        :param file_path: File path on which to test the validators
        :param patterns: Patterns used to initialize validators
        """
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                # Raw string
                validator = self._matcher(pattern)
                # Should raise an error
                # noinspection PyUnresolvedReferences
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))

                # Compiled regular expression
                validator = self._matcher(re.compile(pattern))
                # Should raise an error
                # noinspection PyUnresolvedReferences
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))

    def assert_passes_with_globs(
            self,
            file_path: pathlib.PurePath,
            globs: Iterator[str]
    ):
        """
        Assert that a validator initialized with any of the `globs` doesn't fail
        when executed on `file_path`.

        :param file_path: File path on which to test the validators
        :param globs: Glob patterns used to initialize validators
        """
        for glob in globs:
            with self.subTest(pattern=glob):
                # Raw string
                validator = self._matcher(glob=glob)
                # Should not raise any error
                validator(file_path, str(file_path))

    def assert_fails_with_globs(
            self,
            file_path: pathlib.PurePath,
            globs: Iterator[str]
    ):
        """
        Assert that a validator initialized with any of the `globs` fails when
        executed on `file_path`.

        :param file_path: File path on which to test the validators
        :param globs: Glob patterns used to initialize validators
        """
        for glob in globs:
            with self.subTest(pattern=glob):
                # Raw string
                validator = self._matcher(glob=glob)
                # Should raise an error
                # noinspection PyUnresolvedReferences
                with self.assertRaises(argparse.ArgumentTypeError):
                    validator(file_path, str(file_path))

    def test_raises_if_no_pattern_and_no_glob(self):
        """
        Test initializing the validator raises if we don't specify a pattern nor a glob.
        """
        with self.assertRaises(ValueError):
            self._matcher()

    def test_raises_if_both_pattern_and_glob(self):
        """
        Test initializing the validator raises if we specify both a pattern and a glob.
        """
        with self.assertRaises(ValueError):
            self._matcher("pattern", "glob")

    def test_equality(self):
        """
        Test the __eq__ method compares pattern and glob
        """
        # Test with string pattern

        validator_base = self._matcher("test")
        validator_equal = self._matcher("test")
        validator_ne = self._matcher("test2")

        self.assertEqual(validator_base, validator_base)
        self.assertEqual(validator_base, validator_equal)
        self.assertNotEqual(validator_base, validator_ne)

        # Test with compiled pattern.
        #
        # Note: When creating a new pattern instance using the same pattern string as
        # a previous pattern instance, Python will generally reuse the same instance
        # instead of creating a new instance (see creation of `pattern1` and
        # `pattern2` below). It thus prevents us to create equal but *different*
        # instances of patterns. To prevent this caching, we use re.DEBUG. The debug
        # mode has a side effect of outputting compiled patterns on stdout after
        # compilation. To avoid those messages, we temporarily catch and dismiss any
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
