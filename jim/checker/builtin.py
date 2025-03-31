from collections import ChainMap

import jim.checker.evaluator as checker
from jim.evaluator.execution import EvaluateIn
import jim.evaluator.common_builtin as common
import jim.evaluator.errors as errors
import jim.evaluator.execution as execution
from jim.objects import *
import jim.objects as objects

from jim.debug import debug


builtin_symbols = common.builtin_symbols.copy()

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
		if not all(map(objects.is_known, locals[p[0]])):
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
	"+", "-", "*", "/", "%"}
# Common executions that do not need to go through delegation wrapping.
_pure_commons = {"=", "<", ">", "<=", ">=", "and", "or", "not"}
# Implication cannot be pure (for now) because
# it is implemented as a Macro so it sees unresolved symbols as arguments.
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

for name in _pure_commons:
	pure(type(common.builtin_symbols[name]))


################################################################################


@builtin_symbol("__vmap__")
class ShowVMap(execution.Function):
	def __init__(self):
		super().__init__([])
	def evaluate(self, context):
		print("v-map:", checker.vmap)
		return
		yield


@builtin_symbol("assert")
class Assertion(Execution):
	def __init__(self):
		super().__init__(["assertion", ["value", true]])
	def evaluate(self, context, assertion, value):
		yield from checker.assert_evaluate(assertion, value, context)
		return nil


@builtin_symbol("obtain")
class Reiteration(Execution):
	def __init__(self):
		super().__init__(["conclusion", ["value", true]])
	def evaluate(self, context, conclusion, value):
		f = checker.push(conclusion, context)
		yield
		if not value.equal(f.result):
			raise errors.AssertionError(conclusion)
		return nil


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

	if head.value == "*result*":
		raise errors.JimmyError("Cannot use result as execution in post-conditions.")
		# Because we can't determine if that *result* is a pure function.

	head = checker.evaluate(head, context)
	bs = builtin_symbols  # Basically an alias so we can type less.

	# A progn contributes nothing,
	if head is bs["progn"]:
		# but if it has exactly 1 form for body, check the body.
		if len(rest) == 1:
			return _collect_conditions(context, rest[0], pre_or_post)
		return []

	# Otherwise, the form must be one of precond, postcond, or invar.
	if not (head is bs["precond"] or head is bs["invar"]
			or isinstance(head, common.ParameterizedPostCondition)):
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
		if head is bs["invar"] or isinstance(head, common.ParameterizedPostCondition):
			return conditions + [condition]

	return conditions


class ConditionalMixin:
	def __init__(self, *args, pre_conditions=(), post_conditions=(), **kws):
		super().__init__(*args, **kws)
		self.pre_conditions = tuple(pre_conditions)
		self.post_conditions = tuple(post_conditions)

	def check_preconds(self, context):
		for cond in self.pre_conditions:
			yield from _check_condition(cond, context, fail_msg="Pre-condition failed.")

	# Not actually used. The check happens as part of evaluation.
	def check_postconds(self, start_context, result):
		for cond in self.post_conditions:
			yield from _check_condition(cond, context, fail_msg="Post-condition failed.")


def _check_condition(condition, context, fail_msg):
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
		yield from checker.mark_as_true(condition, masked_context)


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


@builtin_symbol("fn")
class UserFunction(UserExecution):
	# Function definition forms are not pure due to progn body and closure
	# (technically could be pure but too much hassle to pick apart locals
	# and captured closures in the body),
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
			debug("fn check pre-conditions:", self.pre_conditions)
			context = self.closure.new_child(locals)
			yield from self.check_preconds(context)

			if self.verified:
				result = UnknownValue()
			else:
				self.verified = True
				# Mask all input arguments.
				locals = {name: UnknownValue() for name in locals}
				masked_context = self.closure.new_child(locals)
				# Assume the masked arguments satisfies the pre-conditions.
				debug("fn preparing pre-conditions for body:", self.pre_conditions)
				for condition in self.pre_conditions:
					yield from checker.assert_evaluate(condition, true, masked_context)
				# Evaluate body and retrieve return value.
				# Post-conditions are checked as part of evaluation.
				f = checker.push(self.body, masked_context)
				yield
				result = f.result

			# Successful evaluation implies post-conditions are satisfied.
			context["*recur*"] = self
			context["*result*"] = result
			debug("fn sending post-conditions out:", self.post_conditions)
			for condition in self.post_conditions:
				yield from checker.assert_evaluate(condition, true, context)
			return result

	def evaluate(self, context, param_spec, body):
		return super().evaluate(
			context.new_child({"postcond": common.builtin_symbols["postcond"]}),
			param_spec, body)


@builtin_symbol("loop")
class Loop(UserExecution):
	# Not pure because each recur changes the loop variable bindings.
	class Instance(ConditionalMixin, EvaluateIn, UserExecution.Instance):
		def __init__(self, names, body, closure):
			# loop needs parameterized postcond.
			closure = closure.new_child(
					{"postcond": common.ParameterizedPostCondition(names)})
			preconds = _collect_conditions(closure, body, True)
			postconds = _collect_conditions(
					closure.new_child({"*recur*": self}), body, False)
			super().__init__(names, body, closure,
					pre_conditions=preconds, post_conditions=postconds)
			self.alive = True

		def evaluate(self, calling_context, **locals):
			if not self.alive:
				raise errors.JimmyError("Cannot invoke loop iteration outside of loop.")

			# Check pre-conditions on actual arguments.
			yield from self.check_preconds(self.closure.new_child(locals))

			if self.verified:
				result = UnknownValue()
				for name in self.parameter_spec:
					calling_context[name] = UnknownValue()

			else:
				self.verified = True

				# Mask all input arguments.
				locals = {name: UnknownValue() for name in locals}
				body_context = self.closure.new_child(locals)
				body_context["*recur*"] = self

				# Assume the masked arguments satisfies the pre-conditions.
				for condition in self.pre_conditions:
					yield from checker.assert_evaluate(condition, true, body_context)
				# Evaluate body and retrieve return value.
				# Post-conditions are checked as part of evaluation.
				# *result* is available to postcond as postcond handles it internally.
				f = checker.push(self.body, body_context)
				yield
				result = f.result

				# Successful evaluation implies post-conditions are satisfied.
				# ParameterizedPostCondition also handles this part itself,
				# but we need to bring the loop variables back again for assert_evaluate.
				# Unlike for fn, we need to send these bindings to the calling_context,
				# so we can't make a new_child for these names.
				for name in self.parameter_spec:
					calling_context[name] = body_context[name]

			context = calling_context.new_child({"*result*": result, "*recur*": self})
			for condition in self.post_conditions:
				yield from checker.assert_evaluate(condition, true, context)

			return result

	def evaluate(self, context, param_spec, body):
		# Loop instance only accepts positional params corresponding to variables
		# to send back to the calling context.
		def is_symbol(n): return isinstance(n, Symbol)
		if not all(map(is_symbol, param_spec)):
			raise errors.JimmyError("Loop variable is not an identifier.")

		evaluation = super().evaluate(context, param_spec, body)
		try:
			next(evaluation)
		except StopIteration as e:
			loop = e.value

		f = checker.push(List([loop, *param_spec]), context)
		yield
		loop.alive = False
		return f.result


@builtin_symbol("by-cases")
class ExploreIfBranches(Execution):
	def __init__(self):
		super().__init__(["conclusion"])

	class Instance(Execution):
		def __init__(self, conclusion):
			super().__init__(["if_form"])
			self.conclusion = conclusion

		def explore_branch(self, context, condition, branch, assumption):
			# Prepares temporary context and vmap.
			context = context.new_child()
			old_knowns = checker.vmap
			checker.vmap = checker.vmap.new_child()
			# Add branch assumption to vmap.
			try:
				yield from checker.assert_evaluate(condition, assumption, context)
				f = checker.push(branch, context)
				yield
				# Confirm branch yields conclusion.
				yield from _check_condition(self.conclusion, context,
						f"{bool(assumption)} branch failed to produce conclusion.")
			finally:
				# Drop evaluation results from the branch.
				checker.vmap = old_knowns

		def evaluate(self, context, if_form):
			# Confirm if_form is valid:
			# 1) that the form is a list.
			if not isinstance(if_form, List):
				raise errors.JimmyError("Proof-by-cases must consume an if-condition.")
			# 2) that the head of the list is the if-condition execution.
			f = checker.push(if_form.head, context)
			yield
			if f.result is not builtin_symbols["if"]:
				raise errors.JimmyError("Proof-by-cases must consume an if-condition.")
			# 2.a) don't assume the head form was indempotent; avoid re-eval.
			if_form = List([f.result, *if_form.rest])
			# 3) that the form provides the right arguments for the if form.
			try:
				if_parts = execution.fill_parameters(
						builtin_symbols["if"].parameter_spec, if_form.rest)
			except execution.ArgumentMismatchError:
				raise errors.ArgumentMismatchError(if_form) from None

			# All matched up; we have an if-form. Extract condition and branches.
			condition = if_parts["condition"]
			branch_true = if_parts["success"]
			branch_false = if_parts["fail"]

			# Evaluate condition.
			f = checker.push(condition, context)
			yield

			# If condition is unknown, explore branches to find which case
			# the condition must be in based on contradictions.
			if not objects.is_known(f.result):
				branch_true_contrd = branch_false_contrd = false

				# Evalaute true branch.
				try:
					yield from self.explore_branch(context, condition, branch_true, true)
				except errors.ContradictionError:
					debug("Contradiction found in true branch.")
					branch_true_contrd = true

				# Evaluate false branch.
				try:
					yield from self.explore_branch(context, condition, branch_false, false)
				except errors.ContradictionError:
					debug("Contradiction found in false branch.")
					branch_false_contrd = true

				# If both branches gave contradictions,
				# then the condition is both true and false.
				if branch_true_contrd and branch_false_contrd:
					raise errors.ContradictionError(condition, true, false)
				# If only one branch produced a contradiction,
				# then the condition must be in the other case.
				if branch_true_contrd or branch_false_contrd:
					# If there was a contradiction in the true branch,
					# we want the false branch, and branch_false_contrd
					# is also false in that case; vice versa.
					assumption = branch_false_contrd
				# Otherwise, no contradiction in either branch,
				# and both cases satisfied the conclusion.
				else:
					yield from checker.assert_evaluate(self.conclusion, true, context)
					return UnknownValue()

			else:  # Condition is known.
				if not isinstance(f.result, Bool):
					raise ValueError(f.result, "Value must be either true or false.")
				assumption = f.result

			# The previous lengthy if-statement has now found the branch
			# the condition would have picked. Evaluate that branch.
			branch = branch_true if assumption else branch_false
			yield from checker.assert_evaluate(condition, assumption, context)
			f = checker.push(branch, context)
			yield
			result = f.result
			# Check conclusion.
			yield from _check_condition(self.conclusion, context,
					f"{bool(condition)} branch failed to produce conclusion.")
			yield from checker.assert_evaluate(self.conclusion, true, context)
			return result

	def evaluate(self, context, conclusion):
		return self.Instance(conclusion)
		yield
