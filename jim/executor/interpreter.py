from contextlib import contextmanager

import jim.executor.builtins as jimlang
import jim.executor.execution as jexec
from .errors import *
from jim.objects import *


class Context:
	def __init__(self, enclosing_context, **bindings):
		self.enclosing_context = enclosing_context
		self.symbol_table = dict(**bindings)

	def lookup(self, name):
		try:
			return self.symbol_table[name]
		except KeyError as e:
			if self.enclosing_context is not None:
				return self.enclosing_context.lookup(name)
			raise UndefinedVariableError(name) from e

	def __getitem__(self, key):
		return self.symbol_table[key]

	def __setitem__(self, key, val):
		self.symbol_table[key] = val

	def __iter__(self):
		return iter(self.symbol_table.items())

	def copy(self):
		return Context(self.enclosing_context, **self.symbol_table)


class Stackframe:
	def __init__(self, last_frame, call_form, base_context):
		self.last_frame = last_frame
		self.call_form = call_form
		self.context = base_context

	def push_context(self):
		self.context = Context(self.context)
	def pop_context(self):
		self.context = self.context.enclosing_context

	@contextmanager
	def new_context(self):
		self.push_context()
		try:
			yield self.context
		finally:
			self.pop_context()

	@contextmanager
	def switch_context(self, context):
		saved = self.context
		self.context = context
		try:
			yield context
		finally:
			self.context = saved


top_frame = Stackframe(None, "base frame", Context(None))
# initialize builtins
top_frame.context.symbol_table.update(jimlang.builtin_symbols)


def iter_stack():
	f = top_frame
	while f is not None:
		yield f
		f = f.last_frame


@contextmanager
def push_new_frame(call_form, base_context):
	#print(f"DEBUG: PUSH: {call_form}")
	global top_frame
	top_frame = Stackframe(top_frame, call_form, base_context)
	try:
		yield top_frame
	except:
		raise
	finally:
		top_frame = top_frame.last_frame
		#print(f"DEBUG: POP: {call_form}")


def switch_context(context):
	return top_frame.switch_context(context)


def evaluate(obj):
	"""Computes a value for the form parsed by reader."""

	#print(f"DEBUG: evaluate: {obj}")

	match obj:
		# These objects are self-evaluating.
		case Integer() | String() | Array() | jexec.Execution() | jimlang.nil:
			return obj

		case Symbol(value=name):
			return top_frame.context.lookup(name)

		case CompoundForm(children=forms):
			if len(forms) == 0:
				return jimlang.nil
			return invoke(obj)

		case _:
			for i, frame in enumerate(reversed(list(iter_stack()))):
				print(f"DEBUG: {i}: {frame.call_form}")
			print(f"DEBUG: raw object: {obj}")
			assert False  # We should never see raw python object.


def invoke(compound_form):
	execution = evaluate(compound_form.head)
	args = compound_form.rest

	if not isinstance(execution, jexec.Execution):
		raise JimmyError("Invocation target is invalid.", compound_form)

	if isinstance(execution, jexec.EvaluateIn):
		args = map(evaluate, args)

	#print(f"DEBUG: invoke: {compound_form}")

	try:
		matched_params = jexec.fill_parameters(execution.parameter_spec, args)
	except jexec.ArgumentMismatchError:
		raise ArgumentMismatchError(compound_form) from None

	# The context should be determined by execution:
	# def form needs context to be the outer context,
	# function calls need to switch to the function closure.
	context = execution.context(matched_params)
	with push_new_frame(compound_form, context) as f:
		result = execution.evaluate(context, **matched_params)

	if isinstance(execution, jexec.EvaluateOut):
		return evaluate(result)
	else:
		return result
