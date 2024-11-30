from abc import ABC, abstractmethod
from contextlib import contextmanager

import jim.evaluator.execution as jexec
from .errors import *
from jim.objects import *


class AbstractContext(ABC):
	@abstractmethod
	def __init__(self, parent, bindings={}):
		pass
	@abstractmethod
	def __getitem__(self, name):
		pass
	@abstractmethod
	def __setitem__(self, key, val):
		pass


class Stackframe:
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
	#print(f"DEBUG: PUSH: {call_form}")
	global top_frame
	top_frame = Stackframe(top_frame, call_form)
	try:
		yield top_frame
	except:
		raise
	finally:
		top_frame = top_frame.last_frame
		#print(f"DEBUG: POP: {call_form}")


def evaluate(obj, context):
	"""
	Evaluates a form under the specified context.
	Returns the evaluated value; the context may be mutated as part of evaluation.
	"""

	#print(f"DEBUG: evaluate: {obj}")

	import jim.objects  # specifically for the nil match below
	match obj:
		# These objects are self-evaluating.
		case (True | False | jim.objects.nil
				| Integer() | String() | jexec.Execution()):
			return obj

		case Symbol(value=name):
			return context[name]

		case List():
			if len(obj) == 0:
				return nil
			try:
				return invoke(obj, context)
			except JimmyError:
				raise
			except Exception as e:
				raise JimmyError(str(e), obj)

		case _:
			for i, frame in enumerate(reversed(list(iter_stack()))):
				print(f"DEBUG: {i}: {frame.call_form}")
			print(f"DEBUG: raw object: {obj}")
			assert False  # We should never see raw python object.


def invoke(lst, context):
	execution = evaluate(lst[0], context)
	args = lst[1:]

	if not isinstance(execution, jexec.Execution):
		raise JimmyError("Invocation target is invalid.", lst)

	if isinstance(execution, jexec.EvaluateIn):
		args = map(lambda arg: evaluate(arg, context), args)

	#print(f"DEBUG: invoke: {lst}")

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
