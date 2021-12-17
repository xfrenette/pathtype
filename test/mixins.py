import argparse
import contextlib
from typing import Optional
from unittest.mock import patch, Mock


class ArgparseTester:
    """
    Mixin for unitest.TestCase classes that validate the argparser.
    """

    @contextlib.contextmanager
    def assert_argparse_error(self, parser: argparse.ArgumentParser,
                              msg: Optional[str] = None):
        """
        Context manager that asserts, on exit, that the parser ended in error.

        If, by the end of this context manager, code execution didn't trigger
        a parser error (ex: `parser.parse_args` failing), an assert exception is
        raised.

        Note that as soon as the parser triggers an error, the rest of the code
        block won't be executed and the context manager will be exited.

        As a side effect, this context manager also prevents the parser to
        output its usual error messages on stderr.

        Example
        >>> parser = argparse.ArgumentParser()
        >>> parser.add_argument("--valid")
        >>> with self.assert_argparse_error(parser):
        >>>     parser.parse_args(["--invalid"])
        >>>     # The following line won't be executed since the previous
        >>>     # parsing triggered an error which exited the context manager.
        >>>     print("Never reached")

        :param parser: Argument parser to test
        :param msg: Message to show on failure (i.e. if the parser doesn't
            trigger an error)
        """
        msg = msg or "Expected the parser to fail"

        def error(*args, **kwargs):
            raise SystemExit

        mock_error: Optional[Mock] = None
        try:
            with patch.object(parser, "error") as _mock_error:
                _mock_error.side_effect = error
                mock_error = _mock_error
                yield
        except SystemExit:
            pass
        finally:
            if mock_error.call_count == 0:
                # noinspection PyUnresolvedReferences
                self.fail(msg)
