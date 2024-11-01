import jim.executor.execution as jexec
import jim.executor.interpreter as interpreter
import jim.executor.errors as errors
from jim.ast import *

from functools import reduce
import operator as ops


# TODO make this immutable (outside this module)
builtin_symbols = {
	"True": True,
	"False": False
}

def builtin_symbol(name):
	def reg_symbol(cls):
		cls.__str__ = lambda self: name
		builtin_symbols[name] = cls()
		return cls
	return reg_symbol


@builtin_symbol("nil")
class Nil:
	pass
nil = builtin_symbols["nil"]


def _truthy(v):
	return not (v is nil or v is False)


def _wrap_progn(forms):
	return CompoundForm([Symbol("progn"), *forms])


def _unwrap_int(form: Integer) -> int:
	if not isinstance(form, Integer):
		raise errors.JimmyError("Value is not an integer.", form)
	return form.value


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
		def evaluate(self, context, **locals):
			return conversion(eval_impl(**locals))
		# Creates a class of the same name, with Function as parent.
		return type(evaluate.__name__, (jexec.Function,),
				{ '__init__': __init__, 'evaluate': evaluate })
	return decorator


@builtin_symbol("assert")
@function_execution("expr")
def Assertion(expr):
	if not _truthy(expr):
		raise errors.AssertionError(expr)
	return nil


@builtin_symbol("number?")
@function_execution("value")
def NumberTest(value):
	return isinstance(value, Integer)


@builtin_symbol("def")
class Definition(jexec.Execution):
	def __init__(self):
		super().__init__(["lhs", "rhs"])

	def evaluate(self, context, lhs, rhs):
		match lhs:
			case Symbol(value=symbol):
				lhs = symbol
			case _:
				raise errors.JimmyError("Definition target is not an identifier.", lhs)

		rhs = interpreter.evaluate(rhs)
		context[lhs] = rhs
		return rhs


@builtin_symbol("fn")
class Function(jexec.Execution):
	def __init__(self):
		super().__init__(["param_spec", ["body"]])

	def evaluate(self, context, param_spec, body):
		param_spec_parsed = []
		for p in param_spec:
			match p:
				case Symbol(value=symbol):  # positional
					param_spec_parsed.append(symbol)
				case CompoundForm(children=[Symbol(value=symbol)]):  # rest
					param_spec_parsed.append([symbol])
				case _:
					raise errors.JimmyError(
							"The parameter specification is invalid.", param_spec)
		return jexec.JimmyFunction(param_spec_parsed, body, context)


@builtin_symbol("progn")
class Progn(jexec.Execution):
	def __init__(self):
		super().__init__([["forms"]])

	def evaluate(self, context, forms):
		result = nil
		for form in forms:
			result = interpreter.evaluate(form)
		return result


@builtin_symbol("cond")
class Conditional(jexec.Macro):
	def __init__(self):
		# (cond
		#   ((test1) things...)
		#   ((test2) things...))
		super().__init__([["branches"]])

	def evaluate(self, context, branches):
		for b in branches:
			match b:
				case CompoundForm(children=[test, *body]):
					if _truthy(interpreter.evaluate(test)):
						return _wrap_progn(body)
				case _:
					raise errors.JimmyError("Invalid conditional branch.", b)
		return nil


@builtin_symbol("while")
class WhileLoop(jexec.Execution):
	def __init__(self):
		super().__init__(["test", ["body"]])
	def evaluate(self, context, test, body):
		result = nil
		progn_body = _wrap_progn(body)
		while _truthy(interpreter.evaluate(test)):
			result = interpreter.evaluate(progn_body)
		return result


@builtin_symbol("+")
@function_execution(["terms"], conversion=Integer)
def Addition(terms):
	return sum(map(_unwrap_int, terms))


@builtin_symbol("-")
@function_execution("n", ["terms"], conversion=Integer)
def Subtraction(n, terms):
	n, *terms = map(_unwrap_int, [n] + terms)
	if len(terms) == 0:
		return -n
	return n - sum(terms)


@builtin_symbol("*")
@function_execution(["terms"], conversion=Integer)
def Multiplication(terms):
	return product(map(_unwrap_int, terms))


@builtin_symbol("/")
@function_execution("n", ["terms"], conversion=Integer)  # TODO implement rationals
def Division(n, terms):
	n, *terms = map(_unwrap_int, [n] + terms)
	try:
		if len(terms) == 0:
			return 1 // n
		return n // product(terms)
	except ZeroDivisionError:
		raise errors.DivideByZeroError


@builtin_symbol("%")
@function_execution("x", "y", conversion=Integer)
def Modulo(x, y):
	x, y = _unwrap_int(x), _unwrap_int(y)
	if y == 0:
		raise errors.DivideByZeroError()
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
def Equality(a, b, more):
	a, b, *more = map(_unwrap_int, [a, b, *more])
	return _transitive_property(ops.eq, a, b, more)


@builtin_symbol("<")
@function_execution("a", "b", ["more"])
def LessThan(a, b, more):
	a, b, *more = map(_unwrap_int, [a, b, *more])
	return _transitive_property(ops.lt, a, b, more)


@builtin_symbol(">")
@function_execution("a", "b", ["more"])
def GreaterThan(a, b, more):
	a, b, *more = map(_unwrap_int, [a, b, *more])
	return _transitive_property(ops.gt, a, b, more)


@builtin_symbol("<=")
@function_execution("a", "b", ["more"])
def LessEqual(a, b, more):
	a, b, *more = map(_unwrap_int, [a, b, *more])
	return _transitive_property(ops.le, a, b, more)


@builtin_symbol(">=")
@function_execution("a", "b", ["more"])
def GreaterEqual(a, b, more):
	a, b, *more = map(_unwrap_int, [a, b, *more])
	return _transitive_property(ops.ge, a, b, more)


# Empty conjunction is vacuously true.
# (and) always holds as an axiom.
@builtin_symbol("and")
class Conjunction(jexec.Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, context, terms):
		result = True
		for t in terms:
			result = interpreter.evaluate(t)
			if not _truthy(result):
				return result
		return result


# Empty disjunction is vacuously false.
# (or ...) is true iff there exists an argument which is true;
# an empty (or) has no argument which is true.
# (not (or)) always holds as an axiom.
@builtin_symbol("or")
class Disjunction(jexec.Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, context, terms):
		result = False
		for t in terms:
			result = interpreter.evaluate(t)
			if _truthy(result):
				return result
		return result


@builtin_symbol("not")
@function_execution("p")
def Negation(p):
	return not _truthy(p)


@builtin_symbol("print")
@function_execution("msg")
def Print(msg):
	print(msg)
	return nil


@builtin_symbol("list")
@function_execution(["elements"])
def List(elements):
	return CompoundForm(elements)


@builtin_symbol("list?")
@function_execution("form")
def ListTest(form):
	return isinstance(form, CompoundForm)


@builtin_symbol("get")
@function_execution("lst", "idx")
def Get(lst, idx):
	idx = _unwrap_int(idx)
	if not (0 <= idx < len(lst)):
		raise errors.IndexError
	return lst[idx]


@builtin_symbol("rest")
@function_execution("lst")
def Rest(lst):
	return CompoundForm(lst[:-1])


@builtin_symbol("conj")
@function_execution(["lists"])
def Conjoin(lists):
	raw_lists = map(lambda l: list(l.children), lists)
	return CompoundForm(reduce(ops.add, raw_lists, []))


@builtin_symbol("assoc")
@function_execution("lst", "idx", "val")
def Associate(lst, idx, val):
	idx = _unwrap_int(idx)
	if not (0 <= idx < len(lst)):
		raise errors.IndexError
	copy = list(lst.children)
	copy[idx] = val
	return CompoundForm(copy)


@builtin_symbol("count")
@function_execution("lst")
def Count(lst):
	return Integer(len(lst))
