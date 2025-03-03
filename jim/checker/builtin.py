import jim.checker.evaluator as checker
from jim.evaluator.execution import EvaluateIn
import jim.evaluator.common_builtin as common
import jim.evaluator.errors as errors
from jim.objects import *
import jim.objects as objects


# An execution is considered "pure" if
#   - it always returns the same values # for the same arguments, and
#   - it is side-effect free.
pure_functions = {
	type(common.builtin_symbols["and"]),
	# TODO list builtins here.
}

def pure(cls):
	pure_functions.add(cls)
	return cls

def is_pure_function(execution):
	return type(execution) in pure_functions

def is_pure_form(form):
	match form:
		case Atom() | List(elements=[]):
			return True
		case List(elements=[execution, *args]):
			return is_pure_function(execution) and all(map(is_pure_form, args))
		case _:
			return False


def collect_conditions(progn_like):
	# Empty form contributes nothing.
	if len(progn_like) == 0:
		return ([], [])

	head, *rest = progn_like

	# A progn contributes nothing,
	if head is builtin_symbols["progn"]:
		# but if it has exactly 1 form for body, check the body.
		if len(rest) == 1:
			return collect_conditions(rest[0])
		return ([], [])

	# Otherwise, the form must be one of precond, postcond, or invar.
	if head not in list(map(builtin_symbols.get, ["precond", "postcond", "invar"])):
		return ([], [])

	if len(rest) == 0:  # Not a valid condition.
		return ([], [])

	# If a pre or postcond has exactly 1 form for body, check that.
	if len(rest) == 2:
		pre, post = collect_conditions(rest[1])
	else:  # No body (only condition) or more forms for body.
		pre, post = [], []

	condition = rest[0]
	if not is_pure_form(condition):
		raise errors.JimmyError("Condition must be pure.", condition)

	if head is builtin_symbols["precond"]:
		return ([condition] + pre, post)
	if head is builtin_symbols["postcond"]:
		return (pre, post + [condition])
	if head is builtin_symbols["invar"]:
		return ([condition] + pre, post + [condition])

	return ([], [])


class ConditionalMixin:
	def __init__(self, *args, pre_conditions=(), post_conditions=(), **kws):
		super().__init__(*args, **kws)
		self.pre_conditions = tuple(pre_conditions)
		self.post_conditions = tuple(post_conditions)

	def check_preconds(self, context):
		yield from _check_conditions(self.pre_conditions, context,
				fail_msg="Pre-condition failed.")

	# Not actually used. The check happens as part of evaluation.
	def check_postconds(self, start_context, result):
		yield from _check_conditions(self.post_conditions, context,
				fail_msg="Post-condition failed.")


def _check_conditions(conditions, context, fail_msg):
	# Recursion in pre-/post-conditions is allowed, but never called.
	# No special handling is necessary.
	for condition in conditions:
		f = push(condition, context)
		yield
		if not objects.truthy(f.result):
			raise errors.AssertionError(condition, msg=fail_msg)


def _make_truths(conditions, context, mask=None):
	"""
	Make the list of conditions to evaluate to true under the given context.
	"""
	masked_context = context if mask is None else context.new_child(mask)
	for condition in conditions:
		# Compute condition with unknowns and set the result to be true.
		f = push(condition, masked_context)
		yield
		f.result = true
		assert_evaluation(f.invocation_form, true)


class UserExecution(common.UserExecution):
	class Instance(common.UserExecution.Instance):
		def __init__(self, parameter_spec, body, closure):
			super().__init__(parameter_spec, body, closure)
			# A verified execution is no longer called:
			# only the pre-conditions are checked
			# and an unknown with the correct post-conditions is returned.
			# This is True once we start to prove a function.
			# It is safe and necessary to do so for recursion.
			self.verified = False


@common.builtin_symbol("fn")
class UserFunction(UserExecution):
	# Function definition forms are not pure due to progn body and closure,
	# but instances of functions are pure (for now).
	@pure
	class Instance(ConditionalMixin, EvaluateIn, UserExecution.Instance):
		def __init__(self, parameter_spec, body, closure):
			super().__init__(parameter_spec, body, closure)

		def evaluate(self, calling_context, **locals):
			context = self.closure.new_child(locals)
			yield from self.check_preconds(context)

			if self.verified:
				result = UnknownValue()
			else:
				self.verified = True
				locals = {name: UnknownValue() for name in locals}
				yield from _make_truths(self.pre_conditions, self.closure, locals)
				evaluation = super().evaluate(calling_context, **locals)
				try:
					while True:
						yield next(evaluation)
				except StopIteration as e:
					result = e.value

			context["*result*"] = result
			yield from _make_truths(self.post_conditions, context)
			return result


@common.builtin_symbol("loop")
class Loop(UserExecution):
	class Instance(EvaluateIn, UserExecution.Instance):
		def __init__(self, names, body):
			# Loop instance only accepts positional params corresponding to variables
			# to send back to the calling context.
			self.names = list(map(lambda n: n.value, names))
			UserExecution.Instance.__init__(self, self.names, self.body)
			self.alive = True

		def evaluate(self, context, **locals):
			if not self.alive:
				raise errors.JimmyError("Cannot invoke loop iteration outside of loop.")

			body_context = context.new_child(locals)
			body_context["*recur*"] = self
			result = interpreter.evaluate(self.body, body_context)

			for name in self.names:
				context[name] = body_context[name]
			return result

	def __init__(self):
		super().__init__()

	def evaluate(self, context, param_spec, body):
		def is_symbol(n): return isinstance(n, Symbol)
		if not all(map(is_symbol, param_spec)):
			raise errors.JimmyError("Loop variable is not an identifier.")

		loop = Loop.Instance(param_spec, common.wrap_progn(body))
		result = interpreter.evaluate(List([loop, *names]), context)
		loop.alive = False
		return result
