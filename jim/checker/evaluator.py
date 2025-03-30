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
		# Evaluate using the context as usual, then try to update v-map.
		if isinstance(self.form, Symbol):
			self.result = self.context[self.form.value]
			# Trivial case, but we do want to check for immediately contradicting
			# assumptions on the symbols.
			assert_evaluation(self.form, self.result, self.context)
		elif (result := evaluate_simple_form(self.form, self.context)) is not push:
			self.result = result
		else:
			yield from self.evaluate_call_form()
		self.result = vmap.get(resolve_form(self.form, self.context), self.result)

	def evaluate_call_form(self):
		yield from super().evaluate_call_form()
		if builtin.is_pure_function(self.target):
			assert_evaluation(self.form, self.result, self.context)

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


def assert_evaluation(form, value, context=None):
	"""
	Asserts that the form evaluates to the given value and adds it to v-map
	if it is concrete while the previous value is unknown.
	If the form already has a known value,
	then the new value must equal to that value.
	"""
	debug(f"CALL: assert_evaluation({form}, {value})")
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

	# Neither is known; just replacing an unknown with another unknown.
	elif not is_old_known and not is_new_known:
		_replace_value(old, new)
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

def evaluate(obj, context=None):
	return evaluator.evaluate(obj, context)


#class ContextChain(evaluator.DeepCopyChainMap):
#	# The point is to manage Context objects
#	# such that new_child always gets a new Context with updated vmap.
#
#	@property
#	def vmap(self):
#		"""
#		The v-map is a mapping between previously evaluated forms and their values.
#		This is not a cache: its purpose is to track evaluations
#		involving placeholders and to detect contradictions.
#		Since the keys in a v-map are forms with symbols unresolved,
#		there must be a family of v-maps with one for each context.
#		"""
#		return self.maps[0].vmap
#
#	def assert_evaluation(self, form, value):
#		self.maps[0].assert_evaluation(form, value)
#		# TODO When we find a new value for the form (and wasn't a contradiction),
#		# we should update that old value present in the context to the new value.
#
#	def new_child(self, m=None, **kwargs):
#		if m is None:
#			m = kwargs
#		elif kwargs:
#			m.update(kwargs)
#		return self.__class__(Context(m, self.vmap), *self.maps)


#class Context(UserDict):
#	def __init__(self, data=None, vmap=None):
#		if data is None:
#			data = {}
#		if vmap is None:
#			vmap = {}
#		super().__init__()
#		self.vmap = vmap
#		# This updates vmap by calling __setitem__.
#		for k in data:
#			self[k] = data[k]
#
#	def __getitem__(self, name):
#		return self.data[name]
#
#	def __setitem__(self, name, value):
#		self.data[name] = value
#		# Remove every mapping of vmap with name in key.
#		# fn forms, i.e., function definition forms are technically pure forms,
#		# but are difficult to handle here as it is difficult to distinguish
#		# a symbol captured by the closure and a local one
#		# without evaluting the body.
#		for invalided_form in filter(lambda form: name in form, self.vmap):
#			del self.vmap[invalided_form]
