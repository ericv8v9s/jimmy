from collections import ChainMap
from jim.debug import debug, trace_entry, trace_exit

import jim.evaluator.errors as errors
import jim.evaluator.execution as jexec
from jim.objects import *


class DeepCopyChainMap(ChainMap):
	# This exists so that closures are copied correctly.
	def __init__(self, *maps):
		super().__init__(*maps)
	# Don't actually need to override new_child and parents;
	# ChainMap constructs the subclass correctly.
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
		raise errors.UndefinedVariableError(name)
	def __setitem__(self, key, val):
		# Should never happen.
		assert False
	def items(self):
		return ()
	def copy(self):
		return self

stack = []

class Stackframe:
	def __init__(self, form, context):
		self.form = form
		self.context = context
		self.result = None
		self.invocation = self.evaluate_frame()

	def __repr__(self):
		return f"<{self.form}, {self.result}>"

	def evaluate_frame(self):
		"""
		Returns a generator which evaluates the form on the given stackframe,
		yielding whenever another stackframe is pushed on top.
		The result of the call is stored in the result field of the given frame.
		"""
		if isinstance(self.form, Symbol):
			self.result = self.context[self.form.value]
		elif (result := evaluate_simple_form(self.form, self.context)) is not push:
			self.result = result
		else:
			target, *args = self.form

			# Poor man's Future with generators.
			f = push(target, self.context)
			yield
			target = f.result

			if not isinstance(target, Execution):
				raise errors.JimmyError("Invocation target is invalid.", self.form)

			if isinstance(target, jexec.EvaluateIn):
				for i, arg in enumerate(args):
					f = push(arg, self.context)
					yield
					args[i] = f.result

			try:
				matched_args = jexec.fill_parameters(target.parameter_spec, args)
			except jexec.ArgumentMismatchError:
				raise errors.ArgumentMismatchError(self.form) from None

			target_eval = target.evaluate(self.context, **matched_args)
			try:
				while True:
					yield next(target_eval)
			except StopIteration as e:
				self.result = e.value

			if isinstance(target, jexec.EvaluateOut):
				f = push(self.result, self.context)
				yield
				self.result = f.result


class BaseFrame(Stackframe):
	def __init__(self, initial_context):
		super().__init__(nil, initial_context)
	def __repr__(self):
		return "base frame"
	def evaluate_frame(self):
		return
		yield


def init_evaluator(builtins=None):
	if builtins is None:
		from jim.evaluator.common_builtin import builtin_symbols
		builtins = builtin_symbols
	context = DeepCopyChainMap(builtins.copy(), NilContext())
	# Push a dummy frame to initialize the context.
	# Calling evaluate without a context will use the context of the last frame.
	stack.append(BaseFrame(context))


def push(form, context):
	debug(f"CALL: push({form})")
	frame = Stackframe(form, context)
	stack.append(frame)
	return frame

@trace_exit
def pop():
	return stack.pop().result


def evaluate(obj, context=None):
	if context is None:
		context = stack[-1].context

	zero = len(stack)
	# Because we can also call this with a non-empty initial stack
	# in the middle of evaluating an execution.
	push(obj, context)

	while True:
		try:
			next(stack[-1].invocation)
		except StopIteration:
			ret = pop()
			if len(stack) == zero:
				return ret
		except Exception as e:
			while not isinstance(stack[-1], BaseFrame):
				pop()
			# Take the first one that isn't empty.
			#raise errors.JimmyError(str(e) or repr(e) or str(type(e)), obj)
			raise


def evaluate_simple_form(obj, context):
	match obj:
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
