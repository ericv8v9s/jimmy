from jim.objects import *
import jim.objects as objects  # is_mutable, truthy, wrap_bool
from jim.evaluator.execution import Function, Macro
import jim.evaluator.errors as errors
from jim.evaluator.evaluator import push, evaluate

from functools import reduce
import operator as ops


builtin_symbols = {
	"true": true,
	"false": false,
	"nil": nil
}

def builtin_symbol(name):
	def reg_symbol(cls):
		cls.__repr__ = lambda self: name
		builtin_symbols[name] = cls()
		return cls
	return reg_symbol


def wrap_progn(forms):
	if len(forms) == 1:
		return forms[0]
	# also handles edge case of 0 forms
	return List([builtin_symbols["progn"], *forms])


def _unwrap_int(form: Integer) -> int:
	if not isinstance(form, Integer):
		raise errors.JimmyError("Value is not an integer.", form)
	return form.value


def _product(values):  # just like the builtin sum
	return reduce(ops.mul, values, 1)


def _flatten(coll):
	def combine(result, next):
		if isinstance(next, list):
			result.extend(_flatten(next))
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
	def decorator(fn):
		def __init__(self):
			super(type(self), self).__init__(param_spec)
		def evaluate(self, calling_context, **locals):
			return conversion(fn(**locals))
			yield
		# Creates a class of the same name, with Function as parent.
		return type(fn.__name__, (Function,),
				{ '__init__': __init__, 'evaluate': evaluate })
	return decorator


@builtin_symbol("assert")
@function_execution("expr")
def Assertion(expr):
	if not objects.truthy(expr):
		raise errors.AssertionError(expr)
	return nil


@builtin_symbol("number?")
@function_execution("value")
def NumberTest(value):
	return isinstance(value, Integer)


@builtin_symbol("def")
class Definition(Execution):
	def __init__(self):
		super().__init__(["lhs", ["rhs", UnknownValue]])

	def evaluate(self, context, lhs, rhs):
		match lhs:
			case Symbol(value=symbol):
				lhs = symbol
			case _:
				raise errors.JimmyError("Definition target is not an identifier.", lhs)

		if rhs is UnknownValue:
			rhs = UnknownValue()
		else:
			f = push(rhs, context)
			yield
			rhs = f.result
		context[lhs] = rhs
		return rhs


@builtin_symbol("let")
class Let(Execution):
	def __init__(self):
		super().__init__(["bindings", ["forms"]])

	def evaluate(self, context, bindings, forms):
		# bindings should be pairs of names to values, thus must be of even size.
		if not isinstance(bindings, List) or not len(bindings) % 2 == 0:
			raise errors.JimmyError("Bindings definition invalid.", bindings)

		bindings_raw = bindings
		new_context = context.new_child()

		for i in range(0, len(bindings_raw), 2):
			k, v = bindings_raw[i], bindings_raw[i+1]
			if not isinstance(k, Symbol):
				raise errors.JimmyError("Definition target is not an identifier.", k)
			f = push(v, new_context)
			yield
			new_context[k.value] = f.result

		f = push(wrap_progn(forms), new_context)
		yield
		return f.result


class UserExecution(Execution):
	class Instance(Execution):
		def __init__(self, parameter_spec, body, closure):
			Execution.__init__(self, parameter_spec)
			self.body = body
			self.closure = closure

		def evaluate(self, calling_context, **locals):
			f = push(self.body, self.closure.new_child(locals))
			yield
			return f.result

		def __eq__(self, other):
			return False

	def __init__(self):
		super().__init__(["param_spec", ["body"]])

	@staticmethod
	def prepare_param_spec(raw_spec_list, context):
		param_spec = []
		for p in raw_spec_list:
			match p:
				case Symbol(value=name):  # positional
					param_spec.append(name)
				case List(elements=[Symbol(value=name)]):  # rest
					param_spec.append([name])
				case List(elements=[Symbol(value=name), Form() as default]):  # optional
					default = evaluate(default, context)
					if objects.is_mutable(default):
						raise JimmyError("Default argument cannot be or contain a mutable object.")
					else:
						param_spec.append([name, default])
				case _:
					raise errors.JimmyError(
							"The parameter specification is invalid.", p)
		return param_spec

	def evaluate(self, calling_context, param_spec, body):
		execution = self.Instance(
				UserExecution.prepare_param_spec(param_spec, calling_context),
				common.wrap_progn(body),
				closure=calling_context.copy())
		execution.closure["*recur*"] = execution
		return execution
		yield


@builtin_symbol("progn")
class Progn(Execution):
	def __init__(self):
		super().__init__([["forms"]])

	def evaluate(self, context, forms):
		result = nil
		for form in forms:
			f = push(form, context)
			yield
			result = f.result
		return result


@builtin_symbol("precond")
class PreCondition(Macro):
	# (precond condition implicit-progn...)
	def __init__(self):
		super().__init__(["condition", ["forms"]])
	def evaluate(self, context, condition, forms):
		f = push(condition, context)
		yield
		if not objects.truthy(f.result):
			raise errors.AssertionError(condition, msg="Pre-condition failed.")
		return wrap_progn(forms)


@builtin_symbol("postcond")
class PreCondition(Execution):
	def __init__(self):
		super().__init__(["condition", ["forms"]])

	def evaluate(self, context, condition, forms):
		# The post-condition is evaluated under the original context
		# (thus considering the original parameter bindings in a function)
		# and with the special name *result* providing the result value.
		# This is to prove recursion: if the post-condition is dependent
		# on the function internal names, a *recur* call cannot be skipped.
		start_context = context.copy()

		f = push(wrap_progn(forms), context)
		yield
		result = f.result
		start_context["*result*"] = result

		f = push(condition, start_context)
		yield
		if not objects.truthy(f.result):
			raise errors.AssertionError(condition, msg="Post-condition failed.")
		return result


@builtin_symbol("invar")
class Invariant(Macro):
	def __init__(self):
		super().__init__(["condition", ["forms"]])
	def evaluate(self, context, condition, forms):
		return List([
			builtin_symbols["precond"], condition, List([
				builtin_symbols["postcond"], condition, *forms])])
		yield


@builtin_symbol("apply")
class Apply(Macro):
	def __init__(self):
		super().__init__(["f", "args"])
	def evaluate(self, context, f, args):
		f = push(args, context)
		yield
		args_cooked = f.result
		try:
			return List([f, *args_cooked])
		except TypeError:
			return List([f, args_cooked])


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
	return _product(map(_unwrap_int, terms))


@builtin_symbol("/")
@function_execution("n", ["terms"], conversion=Integer)  # TODO implement rationals
def Division(n, terms):
	n, *terms = map(_unwrap_int, [n] + terms)
	try:
		if len(terms) == 0:
			return 1 // n
		return n // _product(terms)
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
	return objects.wrap_bool(result)


@builtin_symbol("=")
@function_execution("a", "b", ["more"])
def Equality(a, b, more):
	a, b, *more = map(_unwrap_int, [a, b, *more])
	return _transitive_property(Form.equal, a, b, more)


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
class Conjunction(Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, context, terms):
		result = true
		for t in terms:
			f = push(t, context)
			yield
			result = f.result
			if not objects.truthy(result):
				return result
		return result


# Empty disjunction is vacuously false.
# (or ...) is true iff there exists an argument which is true;
# an empty (or) has no argument which is true.
# (not (or)) always holds as an axiom.
@builtin_symbol("or")
class Disjunction(Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, context, terms):
		result = false
		for t in terms:
			f = push(t, context)
			yield
			result = f.result
			if objects.truthy(result):
				return result
		return result


@builtin_symbol("not")
@function_execution("p", conversion=objects.wrap_bool)
def Negation(p):
	return not objects.truthy(p)


@builtin_symbol("if")
class Implication(Macro):
	def __init__(self):
		super().__init__(["condition", "success", ["fail", true]])
	def evaluate(self, context, condition, success, fail):
		f = push(condition, context)
		yield
		condition = f.result
		return success if objects.truthy(condition) else fail


@builtin_symbol("print")
@function_execution("msg")
def Print(msg):
	print(msg)
	return nil


@builtin_symbol("list")
@function_execution(["elements"])
def MakeList(elements):
	return List(elements)

#@builtin_symbol("mlist")
#@function_execution(["elements"])
#def MakeMutableList(elements):
#	return MutableList(elements)


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


#@builtin_symbol("assoc!")
#@function_execution("lst", "idx", "val")
#def MutatingAssociate(lst, idx, val):
#	if not isinstance(lst, MutableList):
#		raise errors.JimmyError("Provided list is not mutable.")
#	idx = _unwrap_int(idx)
#	try:
#		lst[idx % len(lst)] = val
#	except ZeroDivisionError:
#		raise errors.IndexError
#	return lst


@builtin_symbol("len")
@function_execution("lst")
def Length(lst):
	return Integer(len(lst))


@builtin_symbol("load")
class Load(Function):
	def __init__(self):
		super().__init__(["path"])

	def evaluate(self, context, path):
		if not isinstance(path, String):
			raise errors.JimmyError("File path is not a string.")
		import jim.reader

		try:
			with open(path.value) as f:
				with jim.reader.fresh_reader_state():
					forms = list(jim.reader.load_forms(lambda: f.read(1)))
		except OSError as e:
			raise errors.LoadError(e)

		for form in forms:
			push(form, context)
			yield
		return nil


@builtin_symbol("__debug__")
@function_execution()
def DebuggerTrigger():
	breakpoint()
