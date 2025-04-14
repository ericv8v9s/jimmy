from collections import ChainMap, UserDict
from jim.debug import trace_entry, debug

import jim.checker.builtin as builtin
import jim.evaluator.evaluator as evaluator
import jim.evaluator.execution as jexec
from jim.evaluator.evaluator import evaluate_simple_form, push
from jim.evaluator.errors import *
import jim.objects as objects
from jim.objects import *


class Stackframe(evaluator.Stackframe):
	@trace_entry
	def evaluate_frame(self):
		# If a value is present before we start, we are given an assumption.
		# That value is to be added to v-map and will take precedence
		# if our evaluation produced an unknown.
		expected_value = self.result

		if isinstance(self.form, Symbol):
			is_call_form = False
			self.result = self.immediate_form = self.context[self.form.value]
		elif (result := evaluate_simple_form(self.form, self.context)) is not push:
			is_call_form = False
			self.result = self.immediate_form = result
		else:
			is_call_form = True
			yield from self.evaluate_call_form()

		if is_call_form:
			if builtin.is_pure_function(self.immediate_form.head):
				update_vmap(self.form, self.result, self.context)
				update_vmap(self.immediate_form, self.result)

		if expected_value is not None:
			update_vmap(self.form, expected_value, self.context)
		self.result = vmap.get(resolve_form(self.form, self.context), self.result)


# Inject our version of evaluate_frame.
evaluator.Stackframe = Stackframe


# The v-map is a mapping between previously evaluated forms and their values.
# This is not a cache: its purpose is to track evaluations
# involving placeholders and to detect contradictions.
# The keys of this mapping are resolved forms, so they are context-indepentent.
vmap = ChainMap()


def resolve_form(form, context):
	"""
	Resolves a form by looking up all names in the provided context.
	Returns the equivalent context-indepentent form,
	or None if the form is too complex to be resolved.
	"""
	# TODO Resolving fn forms is possible with intermediate "closure objects".
	# These form introduce bindings and makes for a complicated analysis
	# (which we won't do).
	# postcond is excluded because it may use the special name *result*.
	banned_targets = {None, *map(builtin.builtin_symbols.get,
			["fn", "loop", "def", "let", "postcond"])}

	match form:
		case Symbol(value=name):
			return context[name]

		case Atom():
			return form

		case List():
			if len(form) == 0:
				return form

			target, *args = form

			target = resolve_form(target, context)
			if target in banned_targets:
				return None
			else:
				args = [resolve_form(arg, context) for arg in args]
				if any(map(lambda arg: arg is None, args)):
					return None
				return List([target, *args])


def update_vmap(form, value, context=None):
	"""
	Asserts that the form evaluates to the given value and adds it to v-map
	if it is concrete while the previous value is unknown.
	If the form already has a known value,
	then the new value must equal to that value.
	"""
	debug(f"CALL: update_vmap({form}, {value})")
	# Assume the provided form to be resolved if no context was given.
	resolved_form = resolve_form(form, context) if context is not None else form
	if resolved_form is None:
		return

	new = value
	old = vmap.get(resolved_form)

	if old is None:
		vmap[resolved_form] = new
		return

	# The idea to prefer known values over unknowns.
	is_old_known = not isinstance(old, UnknownValue)
	is_new_known = not isinstance(new, UnknownValue)

	# Exactly one is known.
	if is_old_known ^ is_new_known:
		if is_old_known:
			known, unknown = old, new
		else:
			known, unknown = new, old
		_replace_value(unknown, known)
		return unknown

	# Neither is known; prefer old value.
	elif not is_old_known and not is_new_known:
		return old

	# Both is known.
	else:
		if old.equal(new):
			if old is not new:
				_replace_value(old, new)
				return old
		else:
			raise ContradictionError(form, old, new)


@trace_entry
def _replace_value(old, new):
	"""
	Replaces the old value with the new one in the v-map.
	Used when the two are shown to be equal.
	"""
	for k, v in vmap.items():
		if v is old:
			vmap[k] = new


#(def c (+ a b))
#(obtain (= (+ c (- a)) (+ (+ a b) (- a))))
#(assoc (+ (+ a b) (- a)))
#(obtain (= (+ (+ a b) (- a)) (+ a b (- a))))
#(commu (+ a b (- a)) (+ a (- a) b))
#(assoc (+ (+ a (- a)) b))
#(neg a)  ; (= 0 (+ a (- a)))
#(obtain (= (+ c (- a)) b))


@trace_entry
def assert_evaluate(form, value, context):
	"""
	Pushes to evaluate the form, mapping the form and its immediate form
	to value in v-map. The result of the evaluation must be unknown
	or equal to the given value.
	"""
	f = push(form, context)
	f.result = value
	yield
	return f.result


def evaluate(obj, context=None):
	return evaluator.evaluate(obj, context)
