import jim.executor.execution as jexec
import jim.executor.interpreter as interpreter
import jim.executor.errors as errors
from jim.ast import *

from functools import reduce
import operator as ops


# TODO make this immutable (outside this module)
symbol_table = {
	"True": True,
	"False": False
}

def builtin_symbol(name):
	def reg_symbol(cls):
		cls.__str__ = lambda self: name
		symbol_table[name] = cls()
		return cls
	return reg_symbol


@builtin_symbol("nil")
class Nil:
	pass
nil = symbol_table["nil"]


def _truthy(v):
	return v is not False


def _wrap_progn(forms):
	return CompoundForm([Symbol("progn"), *forms])


def _unwrap_ints(values: list[Integer]) -> list[int]:
	result = []
	for n in values:
		if not isinstance(n, Integer):
			raise errors.JimmyError(n, "Value is not an integer.")
		result.append(n.value)
	return result


def product(values):  # just like the builtin sum
	return reduce(ops.mul, values, 1)


def flatten(coll):
	def combine(result, next):
		if isinstance(next, list):
			result.extend(flatten(next))
		else:
			result.append(next)
		return result
	return reduce(combine, coll, [])


def function_execution(*param_spec, conversion=lambda x: x):
	"""
	Decorates a function to be an executor.Function class,
	passing through the param_spec to init and using the function
	as the evaluate implementation.
	A conversion function can be specified to be applied to the return value.
	"""
	def decorator(eval_impl):
		def __init__(self):
			super(type(self), self).__init__(param_spec)
		def evaluate(self, frame):
			args = {k: frame[k] for k in flatten(param_spec)}
			return conversion(eval_impl(frame, **args))
		# Creates a class of the same name, with Function as parent.
		return type(evaluate.__name__, (jexec.Function,),
				{ '__init__': __init__, 'evaluate': evaluate })
	return decorator


@builtin_symbol("assert")
@function_execution("expr")
def Assertion(_, expr):
	if not _truthy(expr):
		raise errors.AssertionError(expr)
	return nil


@builtin_symbol("def")
class Definition(jexec.Execution):
	def __init__(self):
		super().__init__(["lhs", "rhs"])

	def evaluate(self, frame):
		match frame["lhs"]:
			case Symbol(value=symbol):
				lhs = symbol
			case _:
				raise errors.SyntaxError(
						frame["lhs"], "Definition target is not a variable.")

		with interpreter.switch_stack(frame.last_frame) as f:
			rhs = interpreter.evaluate(frame["rhs"])
			f.symbol_table[lhs] = rhs

		return rhs


# This is the lambda form.
# There is no defun form. A defun is (def xxx (func ...))
@builtin_symbol("fn")
class Function(jexec.Execution):
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


@builtin_symbol("progn")
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


@builtin_symbol("cond")
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


@builtin_symbol("while")
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


@builtin_symbol("+")
@function_execution(["terms"], conversion=Integer)
def Addition(_, terms):
	terms = _unwrap_ints(terms)
	return sum(terms)


@builtin_symbol("-")
@function_execution("n", ["terms"], conversion=Integer)
def Subtraction(_, n, terms):
	n, *terms = _unwrap_ints([n] + terms)
	if len(terms) == 0:
		return -n
	return n - sum(terms)


@builtin_symbol("*")
@function_execution(["terms"], conversion=Integer)
def Multiplication(_, terms):
	terms = _unwrap_ints(terms)
	return product(terms)


@builtin_symbol("/")
@function_execution("n", ["terms"], conversion=Integer)  # TODO implement rationals
def Division(frame, n, terms):
	n, *terms = _unwrap_ints([n] + terms)
	try:
		if len(terms) == 0:
			return 1 // n
		return n // product(terms)
	except ZeroDivisionError:
		raise errors.DivideByZeroError(frame.call_form)


@builtin_symbol("%")
@function_execution("x", "y", conversion=Integer)
def Modulo(frame, x, y):
	x, y = _unwrap_ints([x, y])
	if y == 0:
		raise errors.DivideByZeroError(frame.call_form)
	return x % y


def _transitive_property(pred, a, b, more):
	result = pred(a, b)
	for t in more:
		if not result:
			break
		a = b
		b = t
		result = pred(a, b)
	return result


@builtin_symbol("=")
@function_execution("a", "b", ["more"])
def Equality(_, a, b, more):
	return _transitive_property(ops.eq, a, b, more)


@builtin_symbol("<")
@function_execution("a", "b", ["more"])
def LessThan(_, a, b, more):
	return _transitive_property(ops.lt, a, b, more)


@builtin_symbol(">")
@function_execution("a", "b", ["more"])
def GreaterThan(_, a, b, more):
	return _transitive_property(ops.gt, a, b, more)


@builtin_symbol("<=")
@function_execution("a", "b", ["more"])
def LessEqual(_, a, b, more):
	return _transitive_property(ops.le, a, b, more)


@builtin_symbol(">=")
@function_execution("a", "b", ["more"])
def GreaterEqual(_, a, b, more):
	return _transitive_property(ops.ge, a, b, more)


# Empty conjunction is vacuously true.
# (and) always holds as an axiom.
@builtin_symbol("and")
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
# (not (or)) always holds as an axiom.
@builtin_symbol("or")
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


@builtin_symbol("not")
@function_execution("p")
def Negation(_, p):
	return not _truthy(p)


@builtin_symbol("print")
@function_execution("msg")
def Print(_, msg):
	print(msg)
	return nil


#@builtin_symbol("list")
#class List(jexec.Function):
#	def __init__(self):
#		super().__init__([["elements"]])
#	def evaluate(self, frame):
#		return frame["elements"]
#
#@builtin_symbol("list-get")
#class ListGet(jexec.Function):
#	def __init__(self):
#		super().__init__(["lst", "idx"])
#	def evaluate(self, frame):
#		lst, idx = frame["lst"], frame["idx"]
#		if not (0 <= idx < len(lst)):
#			raise errors.IndexError(frame.call_form)
#		return lst[idx]
#
#@builtin_symbol("list-set")
#class ListSet(jexec.Function):
#	def __init__(self):
#		super().__init__(["lst", "idx", "val"])
#	def evaluate(self, frame):
#		lst, idx, val = frame["lst"], frame["idx"], frame["val"]
#		if not (0 <= idx < len(lst)):
#			raise errors.IndexError(frame.call_form)
#		lst[idx] = val
#		return val
#
#
#@builtin_symbol("len")
#class Length(jexec.Function):
#	def __init__(self):
#		super().__init__(["sequence"])
#	def evaluate(self, frame):
#		try:
#			return len(frame["sequence"])
#		except TypeError:
#			raise errors.JimmyError(
#				frame.call_form, "Object has no concept of length.")
