from collections import ChainMap
from jim.debug import trace_entry, trace_exit

import jim.checker.builtin as builtin
import jim.evaluator.evaluator as evaluator
import jim.evaluator.execution as jexec
from jim.evaluator.evaluator import evaluate_simple_form, push
from jim.evaluator.errors import *
from jim.objects import *


# The v-map contains known evaluations.
# This is not a cache: its purpose is to track derived evaluations
# involving unknown value placeholders.
# In order to track such evaluation results,
# the just-before-call forms are used as key,
# This is a ChainMap to allow branch exploration and backtrack.
known_evaluations = ChainMap()  


@trace_entry
def replace_value(old, new):
	"""
	Merges the old value with the new one,
	used when the two are shown to be equal.
	This updates all entries in known_evaluations where the old value appears
	and all contexts in the stack.
	Captured closures will not be able to be updated.
	"""
	def _replace_value_in_form(form):
		if isinstance(form, List):
			return List(_replace_value_in_form(c) for c in form)
		if form == old:
			return new
		return form

	for map in known_evaluations.maps:
		for k, v in map.items():
			# Evaluations involving the old value are not deleted
			# to ensure closures still have access to them.
			map[_replace_value_in_form(k)] = _replace_value_in_form(v)

	for frame in evaluator.stack:
		for context in frame.context.maps:
			for k, v in context.items():
				context[k] = _replace_value_in_form(v)


@trace_entry
def assert_evaluation(invocation_form, value):
	"""
	Asserts that the form evaluates to the given value
	and adds it to known_evaluations. If the form already has a known value,
	then the new value must equal to that value.
	"""
	new = value
	old = known_evaluations.get(invocation_form)

	if old is None:
		known_evaluations[invocation_form] = new
		return

	# The idea to prefer known values over unknowns.
	is_old_known = not isinstance(old, UnknownValue)
	is_new_known = not isinstance(new, UnknownValue)

	# Exactly one is known.
	if is_old_known ^ is_new_known:
		if is_old_known:
			keep, drop = old, new
		else:
			keep, drop = new, old
		replace_value(drop, keep)

	# Neither is known.
	# This should really never happen
	# since asserting a form evaluates to unknown is useless.
	elif not is_old_known and not is_new_known:
		replace_value(old, new)

	# Both is known.
	else:
		if old.equal(new):
			if old is not new:
				replace_value(old, new)
		else:
			raise ContradictionError(invocation_form, old, new)


@trace_entry
def evaluate_frame(stackframe):
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
	if builtin.is_pure_function(target):
		try:
			stackframe.result = known_evaluations[stackframe.invocation_form]
			return
		except KeyError:
			pass  # Not found; invoke and add to v-map.

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

	if builtin.is_pure_function(target):
		assert_evaluation(stackframe.invocation_form, stackframe.result)

# Inject our version of evaluate_frame.
evaluator.evaluate_frame = evaluate_frame

#(def c (+ a b))
#(obtain (= (+ c (- a)) (+ (+ a b) (- a))))
#(assoc (+ (+ a b) (- a)))
#(obtain (= (+ (+ a b) (- a)) (+ a b (- a))))
#(commu (+ a b (- a)) (+ a (- a) b))
#(assoc (+ (+ a (- a)) b))
#(neg a)  ; (= 0 (+ a (- a)))
#(obtain (= (+ c (- a)) b))

def evaluate(obj, context):
	return evaluator.evaluate(obj, context)
