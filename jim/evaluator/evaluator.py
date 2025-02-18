from abc import ABC, abstractmethod
from contextlib import contextmanager
from collections import ChainMap

from jim.debug import debug
import jim.evaluator.execution as jexec
from .errors import *
from jim.objects import *


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

def init_context(builtins):
	return ChainMap(builtins.copy(), NilContext())


class Stackframe:
	"""
	Since Python already provides the call stack,
	this doesn't actually do much other than tracking calls
	for a better error message.
	"""
	def __init__(self, last_frame, call_form):
		self.last_frame = last_frame
		self.call_form = call_form

top_frame = None


def iter_stack():
	f = top_frame
	while f is not None:
		yield f
		f = f.last_frame


@contextmanager
def push_new_frame(call_form):
	#debug(f"PUSH: {call_form}")
	global top_frame
	top_frame = Stackframe(top_frame, call_form)
	try:
		yield top_frame
	except:
		raise
	finally:
		top_frame = top_frame.last_frame
		#debug(f"POP: {call_form}")


def evaluate(obj, context):
	"""
	Evaluates a form under the specified context.
	Returns the evaluated value; the context may be mutated as part of evaluation.
	"""

	#debug(f"evaluate: {obj}")

	match obj:
		case Symbol(value=name):
			return context[name]

		# Other atoms are self-evaluating objects.
		case Atom():
			return obj

		case List():
			if len(obj) == 0:
				return nil
			try:
				return invoke(obj, context)
			except JimmyError:
				raise
			except Exception as e:
				# Take the first one that isn't empty.
				raise JimmyError(str(e) or repr(e) or str(type(e)), obj)

		case None:
			# Special case: None means a no-op.
			return None

		case _:
			for i, frame in enumerate(reversed(list(iter_stack()))):
				debug(f"{i}: {frame.call_form}")
			debug(f"raw object: {obj}")
			assert False  # We should never see raw python object.


def invoke(lst, context):
	execution = evaluate(lst[0], context)
	args = lst[1:]

	if not isinstance(execution, Execution):
		raise JimmyError("Invocation target is invalid.", lst)

	if isinstance(execution, jexec.EvaluateIn):
		args = map(lambda arg: evaluate(arg, context), args)

	#debug(f"invoke: {lst}")

	try:
		matched_params = jexec.fill_parameters(execution.parameter_spec, args)
	except jexec.ArgumentMismatchError:
		raise ArgumentMismatchError(lst) from None

	with push_new_frame(lst):
		result = execution.evaluate(context, **matched_params)

	if isinstance(execution, jexec.EvaluateOut):
		return evaluate(result, context)
	else:
		return result
