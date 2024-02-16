import jim.execution as jexec
import jim.interpreter as interpreter
import jim.errors
import jim.utils


class Nil:
	def __str__(self):
		return "nil"
nil = Nil()


def _truthy(v):
	return v is not False


def _wrap_progn(forms):
	return [("SYM", "progn")] + forms


def _require_ints(values):
	for n in values:
		if not isinstance(n, int):
			raise jim.errors.JimmyError(n, "Value is not an integer.")


def product(values):  # just like the builtin sum
	prod = 1
	for n in values:
		prod *= n
	return prod


class Assignment(jexec.Execution):
	def __init__(self):
		super().__init__(["lhs", "rhs"])

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
class Lambda(jexec.Execution):
	def __init__(self):
		super().__init__(["param_spec", ["body"]])

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


class Progn(jexec.Execution):
	def __init__(self):
		super().__init__([["forms"]])

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
		super().__init__([["branches"]])

	def evaluate(self, frame):
		for b in frame["branches"]:
			match b:
				case (test, *body):
					with interpreter.switch_stack(frame.last_frame):
						if _truthy(interpreter.evaluate(test)):
							return _wrap_progn(body)
				case _:
					raise jim.errors.SyntaxError(b, "Invalid conditional branch.")
		return nil


class WhileLoop(jexec.Execution):
	def __init__(self):
		super().__init__(["test-form", ["body"]])
	def evaluate(self, frame):
		test, body = frame["test-form"], frame["body"]
		with interpreter.switch_stack(frame.last_frame):
			result = nil
			progn_body = _wrap_progn(body)
			while _truthy(interpreter.evaluate(test)):
				result = interpreter.evaluate(progn_body)
			return result


class Addition(jexec.Function):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		terms = frame["terms"]
		_require_ints(terms)
		return sum(terms)


class Subtraction(jexec.Function):
	def __init__(self):
		super().__init__(["n", ["terms"]])
	def evaluate(self, frame):
		n = frame["n"]
		terms = frame["terms"]
		_require_ints(terms + [n])

		if len(terms) == 0:
			return -n
		return n - sum(terms)


class Multiplication(jexec.Function):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		terms = frame["terms"]
		_require_ints(terms)
		return product(terms)


class Division(jexec.Function):
	def __init__(self):
		super().__init__(["n", ["terms"]])
	def evaluate(self, frame):
		n = frame["n"]
		terms = frame["terms"]
		_require_ints(terms + [n])

		try:
			if len(terms) == 0:
				return 1 // n
			return n // product(terms)
		except ZeroDivisionError:
			raise jim.errors.DivideByZeroError(frame.call_form)


class Modulo(jexec.Function):
	def __init__(self):
		super().__init__(["x", "y"])
	def evaluate(self, frame):
		x, y = frame["x"], frame["y"]
		_require_ints([x, y])
		if y == 0:
			raise jim.errors.DivideByZeroError(frame.call_form)
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
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a == b, frame["a"], frame["b"], frame["more"])


class LessThan(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a < b, frame["a"], frame["b"], frame["more"])


class GreaterThan(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a > b, frame["a"], frame["b"], frame["more"])


class LessEqual(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a <= b, frame["a"], frame["b"], frame["more"])


class GreaterEqual(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a >= b, frame["a"], frame["b"], frame["more"])


class Conjunction(jexec.Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		result = True
		for t in frame["terms"]:
			with interpreter.switch_stack(frame.last_frame):
				result = interpreter.evaluate(t)
				if not _truthy(result):
					return False
		return result


class Disjunction(jexec.Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		for t in frame["terms"]:
			with interpreter.switch_stack(frame.last_frame):
				result = interpreter.evaluate(t)
				if _truthy(result):
					return result
		return False


class Negation(jexec.Function):
	def __init__(self):
		super().__init__(["p"])
	def evaluate(self, frame):
		return not _truthy(frame["p"])


class Print(jexec.Function):
	def __init__(self):
		super().__init__(["msg"])
	def evaluate(self, frame):
		msg = frame["msg"]
		if isinstance(msg, str):
			print(msg)
		else:
			print(jim.utils.form_to_str(msg))
		return nil


class List(jexec.Function):
	def __init__(self):
		super().__init__([["elements"]])
	def evaluate(self, frame):
		return frame["elements"]

class ListGet(jexec.Function):
	def __init__(self):
		super().__init__(["lst", "idx"])
	def evaluate(self, frame):
		lst, idx = frame["lst"], frame["idx"]
		if not (0 <= idx < len(lst)):
			raise jim.errors.IndexError(frame.call_form)
		return lst[idx]

class ListSet(jexec.Function):
	def __init__(self):
		super().__init__(["lst", "idx", "val"])
	def evaluate(self, frame):
		lst, idx, val = frame["lst"], frame["idx"], frame["val"]
		if not (0 <= idx < len(lst)):
			raise jim.errors.IndexError(frame.call_form)
		lst[idx] = val
		return val


class Length(jexec.Function):
	def __init__(self):
		super().__init__(["sequence"])
	def evaluate(self, frame):
		try:
			return len(frame["sequence"])
		except TypeError:
			raise jim.errors.JimmyError(
				frame.call_form, "Object has no concept of length.")
