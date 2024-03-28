#import jim.executor.execution as jexec
#import jim.executor.interpreter as interpreter
#import jim.executor.errors as errors
from functools import wraps
from jim.syntax import *
from jim.checker.errors import *
from jim.executor.builtins import symbol_table as executor_symbols
from jim.executor.execution import fill_parameters, ArgumentMismatchError


#class Nil:
#	def __str__(self):
#		return "nil"
#nil = Nil()
#
#
#def _truthy(v):
#	return v is not False
#
#
#def _wrap_progn(forms):
#	return CompoundForm([Symbol("progn")] + forms)
#
#
#def _require_ints(values):
#	for n in values:
#		if not isinstance(n, int):
#			raise errors.JimmyError(n, "Value is not an integer.")
#
#
#def product(values):  # just like the builtin sum
#	prod = 1
#	for n in values:
#		prod *= n
#	return prod


rules = dict()

_SAME_NAMED = type('', (), {})  # dummy singleton
def rule_of_inference(name, following=_SAME_NAMED):
	"""
	Decorator that adds the rule to the rules dictionary and adds checks
	against the last form.
	"""
	def reg_rule(func):

		@wraps(func)
		def wrap(proof_level, proposition):
			if following is _SAME_NAMED:
				following = name
			if _check_rule_form_match(name, following, proof_level.last_form):
				return func(proof_level, proposition)
			else:
				raise RuleFormMismatchError(
						proof_level.current_proof_line, name, proof_level.last_form)

		rules[name] = wrap
		return wrap
	return reg_rule


def _check_rule_form_match(rule_name, expected, form):
	if expected is None and form is None:
		return True
	match form:
		case CompoundForm(children=(Symbol(value=head), *rest)):
			if expected != head:
				return False
			try:
				# We don't care about the result.
				# We just want to check that this doesn't fail.
				fill_parameters(executor_symbols[head].parameter_spec, rest)
				return True
			except KeyError | ArgumentMismatchError:
				return False
		case _:
			return False


class Assertion(jexec.Function):
	def __init__(self):
		super().__init__(["expr"])
	def evaluate(self, frame):
		if not _truthy(frame["expr"]):
			raise errors.AssertionError(frame["expr"])
		return nil

@rule_of_inference("assert")
def assertion(pl, prop):
	# at this point, last_form has been checked to be a valid assert form
	...


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
