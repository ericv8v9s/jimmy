import jim.evaluator.evaluator as evaluator


#In calling
#  1: (call 1)
#  2: (call 2)
#  ...
#The evaluation of
#  (offending form)
#failed because
#  message for failure


class JimmyError(Exception):
	def __init__(self, msg, offending_form=None):
		super().__init__()
		self.stackframes = list(evaluator.iter_stack())
		self.msg = msg
		if offending_form is None:
			offending_form = evaluator.top_frame.call_form
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
	def __init__(self, msg="Assertion not satisfied."):
		super().__init__(msg)

class LoadError(JimmyError):
	def __init__(self, cause, msg="Failed to load file."):
		super().__init__(msg + " " + str(cause))


def format_error(e):
	result = "In calling\n"
	for i, f in enumerate(reversed(e.stackframes)):
		result += f"  {i}: {f.call_form}\n"

	result += (
			"The evaluation of\n"
			f"  {e.offending_form!r}\n"
			"Failed because\n"
			f"  {e.msg}")

	return result
