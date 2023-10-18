"""Extension for flake8 that finds usage of print."""
import pycodestyle
import re
import ast
from six import PY2, PY3

try:
    from flake8.engine import pep8 as stdin_utils
except ImportError:
    from flake8 import utils as stdin_utils

__version__ = "4.0.0"

REGEX = "(^print$)|(^pprint$)|(^breakpoint$)|(^peek$)|(^rdb\.celery\(\)$)"

class PrintFinder(ast.NodeVisitor):
    def __init__(self, *args, **kwargs):
        super(PrintFinder, self).__init__(*args, **kwargs)
        self.prints_used = {}
        self.prints_redefined = {}

    def visit_Print(self, node):
        """Only exists in python 2."""
        self.prints_used[(node.lineno, node.col_offset)] = "T001 function found."

    def visit_Call(self, node):
        is_print_function = bool(re.search(REGEX, str(getattr(node.func, "id", None))))
        is_print_function_attribute = (
            bool(re.search(REGEX, str(getattr(getattr(node.func, "value", None), "id", None))))
            and bool(re.search(REGEX, str(getattr(node.func, "attr", None))))
        )
        if is_print_function:
            self.prints_used[(node.lineno, node.col_offset)] = "T001 " + node.func.id + " found."
        elif is_print_function_attribute:
            self.prints_used[(node.lineno, node.col_offset)] = "T001 " + node.func.attr + " found."
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if bool(re.search(REGEX, node.name)):
            self.prints_redefined[(node.lineno, node.col_offset)] = "T001 " + node.name + " found."
        if PY2:
            for arg in node.args.args:
                if bool(re.search(REGEX, arg.id)):
                    self.prints_redefined[(node.lineno, node.col_offset)] = "T001 " + arg.id + " found."
        elif PY3:
            for arg in node.args.args:
                if bool(re.search(REGEX, arg.arg)):
                    self.prints_redefined[(node.lineno, node.col_offset)] = "T001 " + arg.arg + " found."

            for arg in node.args.kwonlyargs:
                if bool(re.search(REGEX, arg.arg)):
                    self.prints_redefined[(node.lineno, node.col_offset)] = "T001 " + arg.arg + " found."
        self.generic_visit(node)

    def visit_Name(self, node):
        if bool(re.search(REGEX, node.id)):
            self.prints_redefined[(node.lineno, node.col_offset)] = "T001 " + node.id + " found."
        self.generic_visit(node)


class PrintChecker(object):
    options = None
    name = "flake8-print"
    version = __version__

    def __init__(self, tree, filename):
        self.tree = tree
        self.filename = filename
        self.lines = None

    def load_file(self):
        if self.filename in ("stdin", "-", None):
            self.filename = "stdin"
            self.lines = stdin_utils.stdin_get_value().splitlines(True)
        else:
            self.lines = pycodestyle.readlines(self.filename)

        if not self.tree:
            self.tree = ast.parse("".join(self.lines))

    def run(self):
        if not self.tree or not self.lines:
            self.load_file()

        parser = PrintFinder()
        parser.visit(self.tree)
        error_dicts = (parser.prints_used, parser.prints_redefined)
        errors_seen = set()

        for index, error_dict in enumerate(error_dicts):
            for error, message in error_dict.items():
                if error in errors_seen:
                    continue

                errors_seen.add(error)
                code = message.split(' ', 1)[0]
                line = self.lines[error[0] - 1]
                line_has_noqa = bool(pycodestyle.noqa(line))

                if line_has_noqa is True and (code in line or "nopep8" in line):
                    continue

                yield (error[0], error[1], message, PrintChecker)
