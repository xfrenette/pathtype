import argparse
import pathlib
import unittest
from typing import Callable, cast, Union
from unittest.mock import Mock

import pathtype
import pathtype.validation as validation
from mixins import ArgparseTester

_ValidationCallable = Callable[[pathlib.Path, str], None]
_imply_exists = ("exists", "writable", "readable", "executable")


def _mock_validation(*args, **kwargs) -> Union[Mock, _ValidationCallable]:
    return cast(_ValidationCallable, Mock(*args, **kwargs))


class TestPathValidator(unittest.TestCase):
    """
    Tests for the `validator` parameter of pathtype.Path's __init__()
    """

    def test_validation_is_optional(self):
        # The following should not raise anything
        pathtype.Path()
        self.assertTrue(True)

    def test_accepts_single_callback(self):
        def callback(*_):
            pass

        # Should not raise anything
        pathtype.Path(validator=callback)
        self.assertTrue(True)

    def test_accepts_iterator_of_callbacks(self):
        def callback(*_):
            pass

        # Should not raise anything
        pathtype.Path(validator=iter([callback, callback]))
        self.assertTrue(True)


class TestPathValidationParameters(unittest.TestCase):
    """
    Tests that the different validation parameters queue the correct validations.
    """

    def test_exists(self):
        """
        Test that the "exists" validation is added to validations, and before custom
        validations.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, exists=True)

        self.assertIsInstance(ptype.validations[0], validation.Exists)
        self.assertEqual(ptype.validations[1], other_validation)
        self.assertEqual(2, len(ptype.validations))

    def test_not_exists(self):
        """
        Test that the "not_exists" validation is added to validations, and before
        custom validations.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, not_exists=True)

        self.assertIsInstance(ptype.validations[0], validation.NotExists)
        self.assertEqual(ptype.validations[1], other_validation)
        self.assertEqual(2, len(ptype.validations))

    def test_exists_and_not_exists(self):
        """
        Test that an error is raised when both `exists` and `not_exists` are used at
        the same time.
        """
        for other_validation in _imply_exists:
            pathtype_args = {other_validation: True, "not_exists": True}
            with self.assertRaises(ValueError):
                pathtype.Path(**pathtype_args)

    def test_readable(self):
        """
        Test that the "readable" validation is added to validations, before custom
        validations, and also that the "exists" is automatically added.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, readable=True)

        self.assertIsInstance(ptype.validations[0], validation.Exists)
        self.assertIsInstance(ptype.validations[1], validation.UserReadable)
        self.assertEqual(ptype.validations[2], other_validation)
        self.assertEqual(3, len(ptype.validations))

    def test_writable(self):
        """
        Test that the "writable" validation is added to validations, before custom
        validations, and also that the "exists" is automatically added.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, writable=True)

        self.assertIsInstance(ptype.validations[0], validation.Exists)
        self.assertIsInstance(ptype.validations[1], validation.UserWritable)
        self.assertEqual(ptype.validations[2], other_validation)
        self.assertEqual(3, len(ptype.validations))

    def test_executable(self):
        """
        Test that the "executable" validation is added to validations, before custom
        validations, and also that the "exists" is automatically added.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, executable=True)

        self.assertIsInstance(ptype.validations[0], validation.Exists)
        self.assertIsInstance(ptype.validations[1], validation.UserExecutable)
        self.assertEqual(ptype.validations[2], other_validation)
        self.assertEqual(3, len(ptype.validations))

    def test_parent_exists(self):
        """
        Test that the "parent_exists" validation is added to validations, and before
        custom validations.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, parent_exists=True)

        self.assertIsInstance(ptype.validations[0], validation.ParentExists)
        self.assertEqual(ptype.validations[1], other_validation)
        self.assertEqual(2, len(ptype.validations))

    def test_parent_exists_ignored_with_exists(self):
        """
        Test that the "parent_exists" is ignored if used with "exists" or other
        validations that imply "exists.
        """
        for other_validation in _imply_exists:
            pathtype_args = {other_validation: True, "parent_exists": True}
            ptype = pathtype.Path(**pathtype_args)
            for ptype_validation in ptype.validations:
                self.assertNotIsInstance(ptype_validation, validation.ParentExists)

    def test_creatable(self):
        """
        Test that the "creatable" validation adds the `ParentUserWritable`
        validation, before custom validations, and also that the "parent_exists" is
        automatically set to True.
        """
        other_validation = _mock_validation()

        # With `exists=False`
        ptype = pathtype.Path(validator=other_validation, creatable=True)
        self.assertIsInstance(ptype.validations[0], validation.ParentExists)
        self.assertIsInstance(ptype.validations[1], validation.ParentUserWritable)
        self.assertEqual(ptype.validations[2], other_validation)
        self.assertEqual(3, len(ptype.validations))

        # With `exists=True`, the `ParentExists` won't be added, but `Exists` will
        ptype = pathtype.Path(validator=other_validation, creatable=True, exists=True)
        self.assertIsInstance(ptype.validations[0], validation.Exists)
        self.assertIsInstance(ptype.validations[1], validation.ParentUserWritable)
        self.assertEqual(ptype.validations[2], other_validation)
        self.assertEqual(3, len(ptype.validations))

    def test_writable_or_creatable(self):
        """
        Test that the "writable_or_creatable" validation adds the expected logical
        validation.
        """
        other_validation = _mock_validation()
        expected_any = validation.Any(
            validation.All(validation.Exists(), validation.UserWritable()),
            validation.All(validation.ParentExists(), validation.ParentUserWritable())
        )

        ptype = pathtype.Path(validator=other_validation, writable_or_creatable=True)
        any_validation = ptype.validations[0]
        self.assertEqual(any_validation, expected_any)
        self.assertEqual(ptype.validations[1], other_validation)
        self.assertEqual(2, len(ptype.validations))

    def test_name_matches_re(self):
        """
        Test that the "name_matches_re" validation adds the correction validation,
        before custom validations.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, name_matches_re="test")
        expected_validation = validation.NameMatches("test")
        self.assertEqual(ptype.validations[0], expected_validation)
        self.assertEqual(ptype.validations[1], other_validation)
        self.assertEqual(2, len(ptype.validations))

    def test_name_matches_glob(self):
        """
        Test that the "name_matches_glob" validation adds the correction validation,
        before custom validations.
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, name_matches_glob="*.txt")
        expected_validation = validation.NameMatches(glob="*.txt")
        self.assertEqual(ptype.validations[0], expected_validation)
        self.assertEqual(ptype.validations[1], other_validation)
        self.assertEqual(2, len(ptype.validations))

    def test_name_matches_re_or_glob(self):
        """
        Test that specifying both "name_matches_re" and "name_matches_glob" raises an
        error.
        """
        with self.assertRaises(ValueError):
            pathtype.Path(name_matches_re="test", name_matches_glob="*.txt")


class TestPathValidations(unittest.TestCase):
    """
    Tests for the instance's `validations` parameter.
    """

    def test_is_empty_list_by_default(self):
        ptype = pathtype.Path()
        self.assertListEqual([], ptype.validations)

    def test_single_callback_in_validator_added(self):
        def callback(*_):
            pass

        ptype = pathtype.Path(validator=callback)
        self.assertListEqual([callback], ptype.validations)

    def test_callback_iter_in_validator_added(self):
        def callback1(*_):
            pass

        def callback2(*_):
            pass

        # Test if an iterable
        validators1 = iter((callback1, callback2, callback1))

        ptype = pathtype.Path(validator=validators1)
        self.assertListEqual([callback1, callback2, callback1], ptype.validations)

        # Test if a regular list
        validators2 = [callback1, callback2, callback1]

        ptype = pathtype.Path(validator=validators2)
        self.assertListEqual([callback1, callback2, callback1], ptype.validations)


class TestPathCallback(unittest.TestCase):
    """
    Test the pathtype.Path's __call__() method.
    """

    def test_returns_path(self):
        arg = "path/to/test"
        expected_path = pathlib.Path(arg)
        ptype = pathtype.Path()
        actual_path = ptype(arg)
        self.assertEqual(expected_path, actual_path)

    def test_executes_validations(self):
        arg = "/path/to/test.tmp"
        expected_path = pathlib.Path(arg)
        validations_called = []

        def validation_callback(label):
            # Returns a "validation" callback that, when called, saves the id
            # in `validations_called`. That way, we can later on check the
            # ids in `validations_called` to know the order in which they
            # were executed.
            def callback(*_):
                validations_called.append(label)
            return callback

        validation1 = _mock_validation(side_effect=validation_callback(1))
        validation2 = _mock_validation(side_effect=validation_callback(2))
        validation3 = _mock_validation(side_effect=validation_callback(3))

        ptype = pathtype.Path(validator=(validation1, validation2))
        ptype.validations.append(validation3)

        ptype(arg)

        # Check that the validations received the correct parameters
        validation1.assert_called_once_with(expected_path, arg)
        validation2.assert_called_once_with(expected_path, arg)
        validation3.assert_called_once_with(expected_path, arg)

        # Check that the validations were called in the correct order.
        self.assertListEqual([1, 2, 3], validations_called)

    def test_raises_if_validation_raises(self):
        def success_validation(*_):
            pass

        def error_validation(*_):
            raise argparse.ArgumentTypeError("Invalid error")

        ptype = pathtype.Path(validator=[success_validation, error_validation])

        with self.assertRaises(argparse.ArgumentTypeError):
            ptype("test")


class TestInsideArgparse(unittest.TestCase, ArgparseTester):
    """
    Test the pathlib.Path inside argparse.
    """

    def test_returns_path(self):
        arg = "/path/to/tmp"
        expected_path = pathlib.Path(arg)

        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathtype.Path())
        args = parser.parse_args(["--path", arg])

        self.assertEqual(expected_path, args.path)

    def test_exits_if_validation_raises(self):
        def validation(*_):
            raise TypeError("test-error")

        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathtype.Path(validator=validation))

        with self.assert_argument_parsing_fails(parser):
            parser.parse_args(["--path", "type"])
