import jim.interpreter

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

class UndefinedVariableError(JimmyError): pass
class DivideByZeroError(JimmyError): pass
class SyntaxError(JimmyError): pass


def format_error(e):
	result = ""
	if len(e.stackframes) != 0:
		result += "In calling\n"
		for i, f in enumerate(e.stackframes):
			result += f"  {i}: {form_to_str(f.call_form)}\n"

	result += (
			"The evaluation of\n"
			f"  {form_to_str(e.offending_form)}\n"
			"failed because\n"
			f"  {e.msg}\n")

	return result


def form_to_str(form):
	if not isinstance(form, list):
		return str(form)
	return "(" + " ".join(map(form_to_str, form)) + ")"
