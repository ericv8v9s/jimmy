from collections import ChainMap

import jim.checker.evaluator as checker
from jim.evaluator.execution import EvaluateIn
import jim.evaluator.common_builtin as common
import jim.evaluator.errors as errors
from jim.objects import *
import jim.objects as objects


builtin_symbols = ChainMap({}, common.builtin_symbols)

def builtin_symbol(name):
	def reg_symbol(cls):
		cls.__repr__ = lambda self: name
		builtin_symbols[name] = cls()
		return cls
	return reg_symbol


################################################################################


# An execution is considered "pure" if
#   - it always returns the same values for the same arguments, and
#   - it is side-effect free.
pure_functions = set()

def pure(cls):
	pure_functions.add(cls)
	return cls

def is_pure_function(execution):
	return type(execution) in pure_functions

def _is_pure_form(context, form):
	match form:
		case Atom() | List(elements=[]):
			return True
		case List(elements=[execution, *args]):
			if not _is_pure_form(context, execution):
				return False
			execution = checker.evaluate(execution, context)
			return is_pure_function(execution)  \
					and all(map(lambda a: _is_pure_form(context, a), args))
		case _:
			return False


################################################################################


def any_unknown(param_spec, locals: dict):
	if not all(map(objects.is_known, locals.values())):
		return True
	# Check the rest param. (Technically there could be more than one.)
	for p in filter(lambda l: not isinstance(l, str) and len(l) == 1, param_spec):
		if not all(map(objects.is_known, locals.values())):
			return True
	return False


def delegate_concrete_to(name):
	"""
	Decorates the execution to the one defined in common_builtin with the same name
	when all arguments are concrete values.
	"""
	def decorator(cls):
		delegation_class = type(common.builtin_symbols[name])
		def __init__(self):
			# Because the target class already knows its own parameter_spec.
			super(type(self), self).__init__()
			self.unknowns_handler = cls()
		def evaluate(self, calling_context, **locals):
			if any_unknown(self.parameter_spec, locals):
				evaluation = self.unknowns_handler.evaluate(calling_context, **locals)
			else:
				evaluation = super(type(self), self).evaluate(calling_context, **locals)
			try:
				while True: yield next(evaluation)
			except StopIteration as e:
				return e.value
		return type(delegation_class.__name__, (delegation_class,),
				{ '__init__': __init__, 'evaluate': evaluate })
	return decorator


# These are the builtins that simply eval to unknown if any argument is unknown.
# Only Functions can be delegated since unevaluated symbols as arguments are not unknowns.
# Omitted builtins either should not or do not need to be delegated.
_delegated_symbols = {
	"number?", "list?", "get", "rest", "conj", "assoc", "len",
	"+", "-", "*", "/", "%", "<", ">", "<=", ">="}
# Implication cannot be pure (for now) because
# by the conditional evaluation necessitated by the nature of "if",
# the evaluation of the form depends on the context.
# TODO It can be pure if we make delayed argument more nuanced than "Macro".

def _add_delegation(name):
	@pure
	@builtin_symbol(name)
	@delegate_concrete_to(name)
	class _DelegatorExecution:
		def evaluate(self, context, **locals):
			return UnknownValue()
			yield

for name in _delegated_symbols:
	_add_delegation(name)


@pure
@builtin_symbol("=")
@delegate_concrete_to("=")
class Equality:
	def evaluate(self, context, a, b, more):
		if not common.transitive_property(Form.equal, a, b, more):
			if all(map(objects.is_known, [a, b, *more])):
				# All values are known and not equal.
				return false
			# Otherwise, some is not known.
			return UnknownValue()
		return true
		yield


################################################################################


def _collect_conditions(context, progn_like, pre_or_post: bool):
	"""
	Collects the pre- or post-conditions from nested forms.
	Pre-donditions are collection if pre_or_post is True,
	and post-conditions if False.
	This is done on a best-effort basis. It is the responsibility of the user
	to specify conditions that can be extracted.
	"""
	try:
		# Empty form contributes nothing.
		if len(progn_like) == 0:
			return []
	except TypeError:
		# Also nothing if it's not a progn-like at all (e.g., a symbol).
		return []

	head, *rest = progn_like

	# If the head is too complex, we are not going to bother.
	if not isinstance(head, Symbol):
		return []

	head = checker.evaluate(head, context)
	bs = builtin_symbols  # Basically an alias so we can type less.

	# A progn contributes nothing,
	if head is bs["progn"]:
		# but if it has exactly 1 form for body, check the body.
		if len(rest) == 1:
			return _collect_conditions(context, rest[0], pre_or_post)
		return []

	# Otherwise, the form must be one of precond, postcond, or invar.
	if head not in [bs["precond"], bs["postcond"], bs["invar"]]:
		return []

	if len(rest) == 0:  # Not a valid condition.
		return []

	# If a pre or postcond has exactly 1 form for body, check that.
	if len(rest) == 2:
		conditions = _collect_conditions(context, rest[1], pre_or_post)
	else:  # No body (only condition) or more forms for body.
		conditions = []

	condition = rest[0]
	if not _is_pure_form(context, condition):
		raise errors.JimmyError("Condition must be pure.", condition)

	if pre_or_post:
		# Only want pre-conditions.
		if head is bs["invar"] or head is bs["precond"]:
			return [condition] + conditions
	else:
		# Only want post-conditions.
		if head is bs["invar"] or head is bs["postcond"]:
			return conditions + [condition]

	return []


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
	for condition in conditions:
		f = checker.push(condition, context)
		yield
		if not objects.known_and_true(f.result):
			raise errors.AssertionError(condition, msg=fail_msg)


def _make_truths(conditions, context, mask=None):
	"""
	Make the list of conditions to evaluate to true under the given context.
	"""
	masked_context = context if mask is None else context.new_child(mask)
	for condition in conditions:
		# Compute condition with unknowns and set the result to be true.
		f = checker.push(condition, masked_context)
		yield
		f.result = true
		checker.assert_evaluation(f.invocation_form, true)


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
			preconds = _collect_conditions(closure, body, True)
			# Recursion only allowed in post-conditions.
			postconds = _collect_conditions(
					closure.new_child({"*recur*": self}), body, False)
			super().__init__(parameter_spec, body, closure,
					pre_conditions=preconds, post_conditions=postconds)

		def evaluate(self, calling_context, **locals):
			# Check pre-conditions on actual arguments.
			context = self.closure.new_child(locals)
			yield from self.check_preconds(context)

			if self.verified:
				result = UnknownValue()
			else:
				self.verified = True
				# Mask all input arguments.
				locals = {name: UnknownValue() for name in locals}
				# Assume the masked arguments satisfies the pre-conditions.
				yield from _make_truths(self.pre_conditions, self.closure, locals)
				# Evaluate body and retrieve return value.
				# Post-conditions are checked as part of evaluation.
				evaluation = super().evaluate(calling_context, **locals)
				try:
					while True:
						yield next(evaluation)
				except StopIteration as e:
					result = e.value

			# Successful evaluation implies post-conditions are satisfied.
			context["*recur*"] = self
			context["*result*"] = result
			yield from _make_truths(self.post_conditions, context)
			return result

	def evaluate(self, context, param_spec, body):
		evaluation = super().evaluate(context, param_spec, body)
		try:
			while True: yield next(evaluation)
		except StopIteration as e:
			execution = e.value
		return execution


@common.builtin_symbol("loop")
class Loop(UserExecution):
	# Not pure because each recur changes the loop variable bindings.
	class Instance(ConditionalMixin, EvaluateIn, UserExecution.Instance):
		def __init__(self, names, body, closure):
			# Loop instance only accepts positional params corresponding to variables
			# to send back to the calling context.
			self.names = list(map(lambda n: n.value, names))
			preconds = _collect_conditions(closure, common.wrap_progn(body), True)
			# Recursion only allowed in post-conditions.
			postconds = _collect_conditions(
					closure.new_child({"*recur*": self}),
					common.wrap_progn(body), False)
			# TODO
			super().__init__(self.names, self.body, closure)
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

		preconds, postconds = _collect_conditions(context, common.wrap_progn(body))
		evaluation = super().evaluate(
				context, param_spec, body,
				pre_conditions=preconds, post_conditions=postconds)
		try:
			while True: yield next(evaluation)
		except StopIteration as e:
			execution = e.value
		return execution

		loop = Loop.Instance(param_spec, common.wrap_progn(body))
		result = interpreter.evaluate(List([loop, *names]), context)
		loop.alive = False
		return result
