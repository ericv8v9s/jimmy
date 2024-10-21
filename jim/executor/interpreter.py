from contextlib import contextmanager

import jim.executor.builtins as jimlang
import jim.executor.execution as jexec
from .errors import *
from jim.ast import *


class Stackframe:
	def __init__(self, last_frame, call_form):
		self.last_frame = last_frame
		self.call_form = call_form
		self.symbol_table = dict()

	def lookup(self, symbol):
		try:
			return self.symbol_table[symbol]
		except KeyError as e:
			if self.last_frame is not None:
				return self.last_frame.lookup(symbol)
			raise UndefinedVariableError(symbol) from e

	def __getitem__(self, key):
		return self.symbol_table[key]


def init_frame_builtins(frame):
	frame.symbol_table.update(jimlang.symbol_table)

top_frame = Stackframe(None, "base frame")
init_frame_builtins(top_frame)


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


@contextmanager
def switch_stack(new_top_frame):
	global top_frame
	saved = top_frame
	top_frame = new_top_frame
	try:
		yield new_top_frame
	except:
		raise
	finally:
		top_frame = saved


def evaluate(form):
	"""Computes a value for the form parsed by reader."""

	#print(f"DEBUG: evaluate( {obj} )")

	match form:
		case Integer() | String():  # These are self-evaluating.
			return form
		case Symbol(value=name):
			return top_frame.lookup(name)

		case CompoundForm(children=forms):
			if len(forms) == 0:
				return jimlang.nil
			return invoke(form)

		case CodeObject():
			# comments and proof annotations are noops
			return None

		case _:
			assert False  # We should never see raw python object.


def invoke(compound_form):
	execution = evaluate(compound_form[0])
	args = compound_form[1:]

	if not isinstance(execution, jexec.Execution):
		raise JimmyError(compound_form, "Invocation target is invalid.")

	if isinstance(execution, jexec.EvaluateIn):
		args = [evaluate(arg) for arg in args]

	#print(f"DEBUG: invoke: ({execution} {args})")

	try:
		matched_params = jexec.fill_parameters(execution.parameter_spec, args)
	except jexec.ArgumentMismatchError:
		raise ArgumentMismatchError(compound_form) from None

	with push_new_frame(compound_form) as f:
		f.symbol_table.update(matched_params)
		result = execution.evaluate(f)

	if isinstance(execution, jexec.EvaluateOut):
		return evaluate(result)
	else:
		return result
