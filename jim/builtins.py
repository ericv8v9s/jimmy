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


class Progn(jexec.Macro):
	def __init__(self):
		super().__init__(["forms"])

	def evaluate(self, frame):
		body = frame["forms"]
		result = nil
		with interpreter.switch_stack(frame.last_frame):
			for form in body:
				result = interpreter.evaluate(form)
		return result


class Conditional(jexec.Macro):
	def __init__(self):
		# (cond
		#   ((test1) things...)
		#   ((test2) things...))
		super().__init__(["branches"])

	def evaluate(self, frame):
		for b in frame["branches"]:
			match b:
				case (test, *body):
					with interpreter.switch_stack(frame.last_frame):
						if interpreter.evaluate(test) is not False:
							# cond body is implicit progn
							body.insert(0, ("SYM", "progn"))
							return body
				case _:
					raise jim.errors.SyntaxError(b, "Invalid conditional branch.")
		return nil


class WhileLoop(jexec.Macro):
	def __init__(self):
		super().__init__("test-form", ["body"])
	def evaluate(self, frame):


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


class Modulo(jexec.Function):
	def __init__(self):
		super().__init__("x", "y")
	def evaluate(self, frame):
		x, y = frame["x"], frame["y"]
		_require_ints([x, y])
		return x % y


def _chain_relation(relation_pred, a, b, more):
		result = relation_pred(a, b)
		for t in more:
			if not result:
				break
			a = b
			b = t
			result = relation_pred(a, b)
		return result


class Equality(jexec.Function):
	def __init__(self):
		super().__init__("a", "b", ["more"])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a == b, frame["a"], frame["b"], frame["more"])


class LessThan(jexec.Function):
	def __init__(self):
		super().__init__("a", "b", ["more"])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a < b, frame["a"], frame["b"], frame["more"])


class GreaterThan(jexec.Function):
	def __init__(self):
		super().__init__("a", "b", ["more"])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a > b, frame["a"], frame["b"], frame["more"])


class LessEqual(jexec.Function):
	def __init__(self):
		super().__init__("a", "b", ["more"])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a <= b, frame["a"], frame["b"], frame["more"])


class GreaterEqual(jexec.Function):
	def __init__(self):
		super().__init__("a", "b", ["more"])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a >= b, frame["a"], frame["b"], frame["more"])


class Conjunction(jexec.Macro):  # TODO should short circuit
	def __init__(self):
		super().__init__(["terms"])
	def evaluate(self, frame):
		result = True
		for t in frame["terms"]:
			with interpreter.switch_stack(frame.last_frame):
				result = interpreter.evaluate(t)
				if result is False:
					return False
		return result


class Disjunction(jexec.Macro):
	def __init__(self):
		super().__init__(["terms"])
	def evaluate(self, frame):
		for t in frame["terms"]:
			with interpreter.switch_stack(frame.last_frame):
				result = interpreter.evaluate(t)
				if result is not False:
					return result
		return False


class Negation(jexec.Function):
	def __init__(self):
		super().__init__("p")
	def evaluate(self, frame):
		return not frame["p"]


class Print(jexec.Function):
	def __init__(self):
		super().__init__("msg")
	def evaluate(self, frame):
		print(jim.utils.form_to_str(frame["msg"]))
		return nil
