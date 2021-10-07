import argparse
import pathlib
import unittest
from typing import Callable, cast, Union
from unittest.mock import Mock

import pathtype
import pathtype.validation as validation

_ValidationCallable = Callable[[pathlib.Path, str], None]


def _mock_validation(*args, **kwargs) -> Union[Mock, _ValidationCallable]:
    return cast(_ValidationCallable, Mock(*args, **kwargs))


class TestPathValidator(unittest.TestCase):
    """
    Tests for the `validator` parameter of __init__
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
    Tests that the different validation parameters correctly set validations
    """

    def test_exists(self):
        """
        Test that the "exist" validation is added to validations, and before
        custom validations
        """
        other_validation = _mock_validation()
        ptype = pathtype.Path(validator=other_validation, exists=True)
        self.assertIsInstance(ptype.validations[0], validation.PathExists)
        self.assertEqual(ptype.validations[1], other_validation)
        self.assertEqual(2, len(ptype.validations))


class TestPathValidations(unittest.TestCase):
    """
    Tests for the instance's `validations` attribute
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
        self.assertListEqual([callback1, callback2, callback1],
                             ptype.validations)

        # Test if a regular list (which is also an "iterable")
        validators2 = [callback1, callback2, callback1]

        ptype = pathtype.Path(validator=validators2)
        self.assertListEqual([callback1, callback2, callback1],
                             ptype.validations)


class TestPathCallback(unittest.TestCase):
    """
    Test the __call__ method
    """

    def test_returns_path(self):
        arg = "path/to/test"
        expected_path = pathlib.Path(arg)
        ptype = pathtype.Path()
        actual_path = ptype(arg)
        self.assertEqual(expected_path, actual_path)

    def test_execute_validations(self):
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


class TestSystem(unittest.TestCase):
    """
    Test the pathlib.Path inside argparse
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

        # argparse doesn't raise an exception when validation fails, instead
        # it exits the program
        with self.assertRaises(SystemExit):
            parser.parse_args(["--path", "type"])
