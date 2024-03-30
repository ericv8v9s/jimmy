from functools import wraps
from jim.syntax import *
from jim.checker.errors import *
import jim.executor.builtins as executor
from jim.executor.execution import fill_parameters, ArgumentMismatchError


rules = dict()

_ANY_FORM = object()
_SAME_NAMED = object()
def rule_of_inference(name, following=_SAME_NAMED):

	def reg_rule(func):
		if following is _ANY_FORM:
			rules[name] = func
			return func

		if following is _SAME_NAMED:
			following = executor.symbol_table[name]

		# otherwise, rule can only apply following the correct form
		@wraps(func)
		def wrap(proof_level, proposition):
			if _check_rule_form_match(following, proof_level.last_form):
				return func(proof_level, proposition)
			else:
				raise RuleFormMismatchError(
						proof_level.current_line, name, proof_level.last_form)
		rules[name] = wrap
		return wrap
	return reg_rule


def _check_rule_form_match(expected, form):
	if expected is None and form is None:
		return True
	match form:
		case CompoundForm(children=(Symbol(value=head), *rest)):
			if executor.symbol_table[head] is not expected:
				return False
			try:
				# We don't care about the result.
				# We just want to check that parameters can be filled.
				fill_parameters(expected.parameter_spec, rest)
				return True
			except ArgumentMismatchError:
				return False
		case _:
			return False


@rule_of_inference("assert")
def assertion(pl, prop):
	pl.results.append(prop)
	assert pl.last_form[1] == prop  # TODO raise ProofError
	return ... # what to return?


class Assignment(jexec.Execution):
	def __init__(self):
		super().__init__(["lhs", "rhs"])

	def evaluate(self, frame):
		match frame["lhs"]:
			case Symbol(value=symbol):
				lhs = symbol
			case _:
				raise errors.SyntaxError(
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
				case Symbol(value=symbol):  # positional
					param_spec.append(symbol)
				case CompoundForm(children=[Symbol(value=symbol)]):  # rest
					param_spec.append([symbol])
				case _:
					raise errors.SyntaxError(
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
				case CompoundForm(children=[test, *body]):
					with interpreter.switch_stack(frame.last_frame):
						if _truthy(interpreter.evaluate(test)):
							return _wrap_progn(body)
				case _:
					raise errors.SyntaxError(b, "Invalid conditional branch.")
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
			raise errors.DivideByZeroError(frame.call_form)


class Modulo(jexec.Function):
	def __init__(self):
		super().__init__(["x", "y"])
	def evaluate(self, frame):
		x, y = frame["x"], frame["y"]
		_require_ints([x, y])
		if y == 0:
			raise errors.DivideByZeroError(frame.call_form)
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


# Empty conjunction is vacuously true.
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


# Empty disjunction is vacuously false.
# (or ...) is true iff any argument is true;
# an empty (or) has no argument which is true.
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
		print(frame["msg"])
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
			raise errors.IndexError(frame.call_form)
		return lst[idx]

class ListSet(jexec.Function):
	def __init__(self):
		super().__init__(["lst", "idx", "val"])
	def evaluate(self, frame):
		lst, idx, val = frame["lst"], frame["idx"], frame["val"]
		if not (0 <= idx < len(lst)):
			raise errors.IndexError(frame.call_form)
		lst[idx] = val
		return val


class Length(jexec.Function):
	def __init__(self):
		super().__init__(["sequence"])
	def evaluate(self, frame):
		try:
			return len(frame["sequence"])
		except TypeError:
			raise errors.JimmyError(
				frame.call_form, "Object has no concept of length.")
