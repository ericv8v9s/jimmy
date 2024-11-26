import jim.evaluator.execution as jexec
from jim.evaluator.evaluator import evaluate
import jim.interpreter.evaluator as interpreter
import jim.evaluator.errors as errors
from jim.objects import *

from functools import reduce
import operator as ops


# TODO make this immutable (outside this module)
builtin_symbols = {
	"True": True,
	"False": False,
	"nil": nil
}

def builtin_symbol(name):
	def reg_symbol(cls):
		cls.__str__ = lambda self: name
		builtin_symbols[name] = cls()
		return cls
	return reg_symbol


def _truthy(v):
	return not (v is nil or v is False)


def _wrap_progn(forms):
	return List([Symbol("progn"), *forms])


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
	Decorates a function to be an execution.Function class,
	passing through the param_spec to init and using the function
	as the evaluate implementation.
	A conversion function can be specified to be applied to the return value.
	"""
	def decorator(eval_impl):
		def __init__(self):
			super(type(self), self).__init__(param_spec)
		def evaluate(self, calling_context, **locals):
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

		rhs = evaluate(rhs, context)
		context[lhs] = rhs
		return rhs


@builtin_symbol("let")
class Let(jexec.Execution):
	def __init__(self):
		super().__init__(["bindings", ["forms"]])

	def evaluate(self, context, bindings, forms):
		# bindings should be pairs of names to values, thus must be of even size.
		if not isinstance(bindings, List) or not len(bindings) % 2 == 0:
			raise errors.JimmyError("Bindings definition invalid.", bindings)

		bindings_raw = bindings
		new_context = interpreter.Context(context)

		for i in range(0, len(bindings_raw), 2):
			k, v = bindings_raw[i], bindings_raw[i+1]
			if not isinstance(k, Symbol):
				raise errors.JimmyError("Definition target is not an identifier.", k)
			new_context[k.value] = evaluate(v, new_context)

		return evaluate(_wrap_progn(forms), new_context)


@builtin_symbol("fn")
class Function(jexec.Execution):
	class Instance(jexec.Function):
		def __init__(self, parameter_spec, code, closure):
			super().__init__(parameter_spec)
			self.code = code
			self.closure = closure

		def evaluate(self, calling_context, **locals):
			context = interpreter.Context(self.closure, locals)
			last = nil
			for form in self.code:
				last = evaluate(form, context)
			return last

	def __init__(self):
		super().__init__(["param_spec", ["body"]])

	def evaluate(self, context, param_spec, body):
		param_spec_parsed = []
		for p in param_spec:
			match p:
				case Symbol(value=symbol):  # positional
					param_spec_parsed.append(symbol)
				case List(elements=[Symbol(value=symbol)]):  # rest
					param_spec_parsed.append([symbol])
				case _:
					raise errors.JimmyError(
							"The parameter specification is invalid.", param_spec)

		closure = context.copy()
		function = Function.Instance(param_spec_parsed, body, closure)
		closure["recur"] = function
		return function


@builtin_symbol("apply")
class Apply(jexec.Macro):
	def __init__(self):
		super().__init__(["f", "args"])

	def evaluate(self, context, f, args):
		args_cooked = evaluate(args, context)
		try:
			return List([f, *args_cooked])
		except TypeError:
			return List([f, args_cooked])


@builtin_symbol("progn")
class Progn(jexec.Execution):
	def __init__(self):
		super().__init__([["forms"]])

	def evaluate(self, context, forms):
		result = nil
		for form in forms:
			result = evaluate(form, context)
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
				case List(elements=[test, *body]):
					if _truthy(evaluate(test, context)):
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
		while _truthy(evaluate(test, context)):
			result = evaluate(progn_body, context)
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
			result = evaluate(t, context)
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
			result = evaluate(t, context)
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
def MakeList(elements):
	return List(elements)


@builtin_symbol("list?")
@function_execution("val")
def ListTest(val):
	return isinstance(form, List)


@builtin_symbol("get")
@function_execution("lst", "idx")
def Get(lst, idx):
	idx = _unwrap_int(idx)
	try:
		return lst[idx % len(lst)]
	except ZeroDivisionError:
		raise errors.IndexError


@builtin_symbol("rest")
@function_execution("lst")
def Rest(lst):
	return List(lst[1:])


@builtin_symbol("conj")
@function_execution(["lists"])
def Conjoin(lists):
	return List(reduce(ops.add, lists, []))


@builtin_symbol("assoc")
@function_execution("lst", "idx", "val")
def Associate(lst, idx, val):
	idx = _unwrap_int(idx)
	copy = list(lst)
	try:
		copy[idx % len(lst)] = val
	except ZeroDivisionError:
		raise errors.IndexError
	return List(copy)


@builtin_symbol("assoc!")
@function_execution("lst", "idx", "val")
def MutatingAssociate(lst, idx, val):
	idx = _unwrap_int(idx)
	try:
		lst[idx % len(lst)] = val
	except ZeroDivisionError:
		raise errors.IndexError
	return lst


@builtin_symbol("count")
@function_execution("lst")
def Count(lst):
	return Integer(len(lst))


@builtin_symbol("load")
@function_execution("path")
def Load(path):
	if not isinstance(path, String):
		raise errors.JimmyError("File path is not a string.")
	import jim.reader

	try:
		with open(path.value) as f:
			with jim.reader.fresh_reader_state():
				forms = list(jim.reader.load_forms(lambda: f.read(1)))
	except OSError as e:
		raise errors.LoadError(e)

	result = nil
	for form in forms:
		result = interpreter.evaluate(form)
	return result


@builtin_symbol("__debug__")
@function_execution()
def DebuggerTrigger():
	breakpoint()
