import jim.interpreter
import jim.utils as utils

#In calling
#  1: (call 1)
#  2: (call 2)
#  ...
#The evaluation of
#  (offending form)
#failed because
#  message for failure


class JimmyError(Exception):
	def __init__(self, offending_form, msg):
		super().__init__()
		self.stackframes = list(jim.interpreter.iter_stack())
		self.offending_form = offending_form
		self.msg = msg

class UndefinedVariableError(JimmyError):
	def __init__(self, symbol, msg="Variable is undefined."):
		super().__init__(symbol, msg)

class DivideByZeroError(JimmyError):
	def __init__(self, offending_form, msg="Cannot divide by zero."):
		super().__init__(offending_form, msg)

class ArgumentMismatchError(JimmyError):
	def __init__(self, offending_form, msg="Arguments do not match the parameters."):
		super().__init__(offending_form, msg)

class IndexError(JimmyError):
	def __init__(self, offending_form, msg="List index is out of bounds."):
		super().__init__(offending_form, msg)

class SyntaxError(JimmyError): pass


def format_error(e):
	result = "In calling\n"
	for i, f in enumerate(reversed(e.stackframes)):
		result += f"  {i}: {utils.form_to_str(f.call_form)}\n"

	result += (
			"The evaluation of\n"
			f"  {utils.form_to_str(e.offending_form)}\n"
			"Failed because\n"
			f"  {e.msg}")

	return result
