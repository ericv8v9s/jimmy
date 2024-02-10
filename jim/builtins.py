import jim.execution as jexec
import jim.interpreter as interpreter
import jim.errors
import jim.utils


class Nil:
	def __str__(self):
		return "nil"
nil = Nil()


def _require_ints(values):
	for n in values:
		if not isinstance(n, int):
			raise jim.errors.JimmyError(n, "Value is not an integer.")


def product(values):  # just like the builtin sum
	prod = 1
	for n in values:
		prod *= n
	return prod


# This is the lambda form.
# There is no defun form. A defun is (assign xxx (func ...))
class Lambda(jexec.Macro):
	def __init__(self):
		super().__init__("param_spec", ["body"])

	def evaluate(self, frame):
		param_spec_raw = frame["param_spec"]
		param_spec = []
		for p in param_spec_raw:
			match p:
				case ("SYM", symbol):  # positional
					param_spec.append(symbol)
				case [("SYM", symbol)]:  # rest
					param_spec.append([symbol])
				case _:
					raise jim.errors.SyntaxError(
							param_spec_raw, "The parameter specification is invalid.")
		return jexec.JimmyFunction(param_spec, frame["body"])


class Addition(jexec.Function):
	def __init__(self):
		super().__init__(["terms"])
	def evaluate(self, frame):
		terms = frame["terms"]
		_require_ints(terms)
		return sum(terms)


class Subtraction(jexec.Function):
	def __init__(self):
		super().__init__("n", ["terms"])
	def evaluate(self, frame):
		n = frame["n"]
		terms = frame["terms"]
		_require_ints(terms + [n])

		if len(terms) == 0:
			return -n
		return n - sum(terms)


class Multiplication(jexec.Function):
	def __init__(self):
		super().__init__(["terms"])
	def evaluate(self, frame):
		terms = frame["terms"]
		_require_ints(terms)
		return product(terms)


class Division(jexec.Function):
	def __init__(self):
		super().__init__("n", ["terms"])
	def evaluate(self, frame):
		n = frame["n"]
		terms = frame["terms"]
		_require_ints(terms + [n])

		if len(terms) == 0:
			return 1 // n
		return n // product(terms)


class Assignment(jexec.Macro):
	def __init__(self):
		super().__init__("lhs", "rhs")

	def evaluate(self, frame):
		match frame["lhs"]:
			case ("SYM", symbol):
				lhs = symbol
			case _:
				raise jim.errors.SyntaxError(
						frame["lhs"], "Assignment target is not a variable.")

		with interpreter.switch_stack(frame.last_frame) as f:
			rhs = interpreter.evaluate(frame["rhs"])
			f.symbol_table[lhs] = rhs

		return rhs


class Print(jexec.Function):
	def __init__(self):
		super().__init__("msg")
	def evaluate(self, frame):
		print(jim.utils.form_to_str(frame["msg"]))
		return nil
