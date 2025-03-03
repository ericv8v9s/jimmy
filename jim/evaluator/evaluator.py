from collections import ChainMap

from .errors import *
import jim.evaluator.execution as jexec
from jim.objects import *
from jim.debug import debug


class DeepCopyChainMap(ChainMap):
	def __init__(self, *maps):
		super().__init__(*maps)
	def copy(self):
		return DeepCopyChainMap(*(m.copy() for m in self.maps))

class NilContext:
	"""
	A dummy dict-like at the end of the context chain
	to raise UndefinedVariableError on failed name lookup.
	"""
	def __init__(self):
		pass
	def __getitem__(self, name):
		raise UndefinedVariableError(name)
	def __setitem__(self, key, val):
		# Should never happen.
		assert False
	def copy(self):
		return self

def init_context(builtins=None):
	if builtins is None:
		from jim.evaluator.common_builtin import builtin_symbols
		builtins = builtin_symbols
	return DeepCopyChainMap(builtins.copy(), NilContext())


stack = []

class Stackframe:
	def __init__(self, form, context):
		self.form = form
		self.invocation_form = form
		self.context = context
		self.invocation = evaluate_frame(self)
		self.result = None

	def __repr__(self):
		return f"<{self.form}, {self.result}>"


def evaluate_frame(stackframe):
	"""
	Returns a generator which evaluates the form on the given stackframe,
	yielding whenever another stackframe is pushed on top.
	The result of the call is stored in the result field of the given frame.
	"""
	result = evaluate_simple_form(stackframe.form, stackframe.context)
	if result is not push:
		stackframe.result = result
		return

	target, *args = stackframe.form

	# Poor man's Future with generators.
	f = push(target, stackframe.context)
	yield
	target = f.result

	if not isinstance(target, Execution):
		raise JimmyError("Invocation target is invalid.", stackframe.form)

	if isinstance(target, jexec.EvaluateIn):
		for i, arg in enumerate(args):
			f = push(arg, stackframe.context)
			yield
			args[i] = f.result

	stackframe.invocation_form = List([target, *args])

	try:
		matched_args = jexec.fill_parameters(target.parameter_spec, args)
	except jexec.ArgumentMismatchError:
		raise ArgumentMismatchError(stackframe.form) from None

	target_eval = target.evaluate(stackframe.context, **matched_args)
	try:
		while True:
			yield next(target_eval)
	except StopIteration as e:
		stackframe.result = e.value

	if isinstance(target, jexec.EvaluateOut):
		f = push(stackframe.result, stackframe.context)
		yield
		stackframe.result = f.result


def push(form, context):
	frame = Stackframe(form, context)
	stack.append(frame)
	return frame

def pop():
	return stack.pop().result


def evaluate(obj, context):
	zero = len(stack)
	# Because we can also call this with a non-empty initial stack
	# in the middle of evaluating an execution.
	push(obj, context)

	while True:
		try:
			next(stack[-1].invocation)
		except JimmyError:
			pop()
			raise
		except StopIteration:
			ret = pop()
			if len(stack) == zero:
				return ret
		except Exception as e:
			# Take the first one that isn't empty.
			raise JimmyError(str(e) or repr(e) or str(type(e)), obj)


def evaluate_simple_form(obj, context):
	match obj:
		case Symbol(value=name):
			return context[name]

		# Other atoms are self-evaluating objects.
		case Atom():
			return obj

		case List():
			if len(obj) == 0:
				return nil

			# Instructs the caller to push and retrieve the result later.
			return push

		case None:
			# Special case: None means a no-op.
			return None

		case _:
			for i, frame in enumerate(stack):
				debug(f"{i}: {frame.form}")
			debug(f"raw object: {obj}")
			assert False  # We should never see raw python object.
