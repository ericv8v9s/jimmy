import jim.checker.interpreter as interpreter
import jim.objects


class JimmyError(Exception):
	def __init__(self, offending_form, msg):
		super().__init__()
		self.stackframes = list(interpreter.iter_stack())
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

class AssertionError(JimmyError):
	def __init__(self, offending_form, msg="Assertion not satisfied."):
		super().__init__(offending_form, msg)

class SyntaxError(JimmyError): pass

class UnknownNamedResultError(JimmyError):
	def __init__(self, name):
		super().__init__(
			jim.objects.Symbol(name), "Symbol does not name a previous result.")

class RuleFormMismatchError(JimmyError):
	def __init__(self, form, last_form, msg=None):
		if msg is None:
			msg = f"Cannot apply rule to form: {last_form}"
		super().__init__(form, msg)

class InvalidRuleApplicationError(JimmyError):
	def __init__(self, form, msg="Failed to produce the specified formula."):
		super().__init__(form, msg)


def format_error(e):
	result = "In calling\n"
	for i, f in enumerate(reversed(e.stackframes)):
		result += f"  {i}: {f.call_form}\n"

	result += (
			"The evaluation of\n"
			f"  {e.offending_form}\n"
			"Failed because\n"
			f"  {e.msg}")

	return result
