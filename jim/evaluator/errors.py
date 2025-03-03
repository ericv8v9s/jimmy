import jim.evaluator.evaluator as evaluator


class JimmyError(Exception):
	def __init__(self, msg, offending_form=None):
		super().__init__()
		self.stackframes = list(evaluator.stack)
		self.msg = msg
		if offending_form is None:
			offending_form = self.stackframes[-1].invocation_form
		self.offending_form = offending_form

class UndefinedVariableError(JimmyError):
	def __init__(self, symbol, msg="Variable is undefined."):
		super().__init__(msg, symbol)

class DivideByZeroError(JimmyError):
	def __init__(self, msg="Cannot divide by zero."):
		super().__init__(msg)

class ArgumentMismatchError(JimmyError):
	def __init__(self, offending_form, msg="Arguments do not match the parameters."):
		super().__init__(msg, offending_form)

class IndexError(JimmyError):
	def __init__(self, msg="Cannot index an empty list."):
		super().__init__(msg)

class AssertionError(JimmyError):
	def __init__(self, assertion, msg="Assertion not satisfied."):
		super().__init__(msg, assertion)

class ContradictionError(JimmyError):
	def __init__(self, form, value1, value2):
		super().__init__(f"Form evaluated to be both {value1!r} and {value2!r}.", form)

class LoadError(JimmyError):
	def __init__(self, cause, msg="Failed to load file."):
		super().__init__(msg + " " + str(cause))


def format_error(e):
	result = "Traceback:\n"
	for i, f in enumerate(e.stackframes):
		result += f"  {i}: {f.form!r}\n"

	result += (
			f"Offending form: {e.offending_form!r}\n"
			f"Cause: {e.msg}")

	return result
