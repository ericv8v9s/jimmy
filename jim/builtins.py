import jim.execution as jexec
import jim.errors


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
# There is no defun form. A defun is (set xxx (func ...))
class Lambda(jexec.Macro):
	def __init__(self):
		super().__init__("param_list", ["body"])
	def evaluate(self, frame):
		return jexec.JimmyProcedure(
				frame.lookup("param_list"),
				frame.lookup("body"))


class Addition(jexec.Function):
	def __init__(self):
		super().__init__(["terms"])
	def evaluate(self, frame):
		terms = frame.lookup("terms")
		_require_ints(terms)
		return sum(terms)


class Subtraction(jexec.Function):
	def __init__(self):
		super().__init__("n", ["terms"])
	def evaluate(self, frame):
		n = frame.lookup("n")
		terms = frame.lookup("terms")
		_require_ints(terms + [n])

		if len(terms) == 0:
			return -n
		return n - sum(terms)


class Multiplication(jexec.Function):
	def __init__(self):
		super().__init__(["terms"])
	def evaluate(self, frame):
		terms = frame.lookup("terms")
		_require_ints(terms)
		return product(terms)


class Division(jexec.Function):
	def __init__(self):
		super().__init__("n", ["terms"])
	def evaluate(self, frame):
		n = frame.lookup("n")
		terms = frame.lookup("terms")
		_require_ints(terms + [n])

		if len(terms) == 0:
			return 1 // n
		return n // product(terms)


class Assign(jexec.Macro):
	def __init__(self):
		super().__init__("lhs", "rhs")
	def evaluate(self):


class Print(jexec.Function):
	def __init__(self):
		super().__init__("msg")
	def evaluate(self, frame):
		print(frame.lookup("msg"), end="")
		return nil
