class _ValueMixin:
	def __init__(self, value, *args, **kws):
		self.value = value
		super().__init__(*args, **kws)

	def __hash__(self):
		return hash(self.value)

	def __eq__(self, other):
		return type(self) is type(other) and self.value == other.value

	def __contains__(self, item):
		return self == item

	def __repr__(self):
		return repr(self.value)

	def __str__(self):
		return str(self.value)


class LanguageObject:
	def __hash__(self):
		pass

	def __eq__(self):
		pass


class Form(LanguageObject):
	"""Notably, comments are language objects but are not forms."""
	def equal(self, other):
		# The concept of equality within the language,
		# which may be changed in the future.
		return self == other


class Atom(_ValueMixin, Form):
	def __init__(self, value):
		super().__init__(value=value)


class _Nil(Atom):
	"""Special singleton nil object."""
	def __init__(self):
		super().__init__(None)
	def __repr__(self):
		return "nil"
	def __str__(self):
		return "nil"
nil = _Nil()


class Bool(Atom):
	pass

class _True(Bool):
	"""Special singleton true object."""
	def __init__(self):
		super().__init__(True)
	def __repr__(self):
		return "true"
	def __str__(self):
		return "true"
	def __bool__(self):
		return True
true = _True()

class _False(Bool):
	"""Special singleton false object."""
	def __init__(self):
		super().__init__(False)
	def __repr__(self):
		return "false"
	def __str__(self):
		return "false"
	def __bool__(self):
		return False
false = _False()


def wrap_bool(b):
	return true if b else false

def known_and_true(v):
	return is_known(v) and v is true


class Integer(Atom):
	pass


class Symbol(Atom):
	def __repr__(self):
		return self.value  # Don't want quotes around symbol names.


class String(Atom):
	_str_escape = str.maketrans({
		'"': '\\"',
		"\\": "\\\\"})
	def __repr__(self):
		return '"' + self.value.translate(self._str_escape) + '"'


class Execution(Atom):
	def __init__(self, parameter_spec):
		super().__init__(self)
		self.parameter_spec = tuple(parameter_spec)

	def __repr__(self):
		return object.__repr__(self)
	def __str__(self):
		return object.__str__(self)
	def __eq__(self, other):
		# Correct for builtins.
		return type(self) == type(other)
	def __hash__(self):
		return object.__hash__(self)

	def evaluate(self, calling_context, **locals):
		# Technically, we don't need locals, as that can exist as another context
		# on top of the provided context.
		# However, every execution defines a parameter_spec and the evaluator
		# already matched up all the arguments before calling evaluate,
		# so as a convenience it is passed on into here.
		# For most builtin executions, this is handy.
		assert False


class UnknownValue(Atom):
	_next_id = 0
	def __init__(self):
		super().__init__(self)
		# Is this thread-safe? No. Do we care? Also no.
		self.id = UnknownValue._next_id
		UnknownValue._next_id += 1
	def __repr__(self):
		return f"unk{self.id}"
	def __str__(self):
		return repr(self)
	def __eq__(self, other):
		return self is other
	def __hash__(self):
		return object.__hash__(self)
	def __bool__(self):
		# Explicitly use is_known instead.
		# This exception can't be caused by user.
		# Any occurrence indicates programming error on our part.
		raise ValueError("UnknownValue does not have definite truth value.")

def is_known(value):
	return not isinstance(value, UnknownValue)


class List(list, Form):
	def __init__(self, elements=None):
		list.__init__(self, [] if elements is None else elements)
		Form.__init__(self)
		self.elements = self  # to make this work with match statements
	def __repr__(self):
		return '(' + " ".join(map(repr, self)) + ')'
	def __str__(self):
		return '(' + " ".join(map(str, self)) + ')'
	def __hash__(self):
		# To allow usage as dict keys.
		return hash(tuple(self))
	def __contains__(self, item):
		return super().__contains__(item) or any(item in e for e in self.elements)

	@property
	def head(self):
		return self[0] if len(self) > 0 else nil

	@property
	def rest(self):
		return List(self[1:]) if len(self) > 0 else List()


#class MutableList(List):
#	def __init__(self, elements=None):
#		super().__init__(elements)


class Comment(_ValueMixin, LanguageObject):
	def __init__(self, content):
		super().__init__(value=content)
	def __str__(self):
		return ";" + self.value + "\\n"


def is_leaf(node):
	try:
		iter(node)
		return False
	except TypeError:
		return True


def filter_tree(tree, criteria):
	"""
	Filter for nodes meeting the criteria.
	The tree must take the form of nested iterables,
	where iterables are internal nodes, or otherwise considered a leaf.
	Tree nodes are not mutated: the modified tree are rebuilt bottom up.
	To do so, all non-leaf nodes must allow construction by passing an
	iterable of children.
	If the root fails the criteria, None is returned.
	"""

	_REMOVED = object()

	def not_removed(x):
		return x is not _REMOVED

	def _filter_tree(tree):
		if not criteria(tree):
			return _REMOVED
		if is_leaf(tree):
			return tree
		else:
			return type(tree)(filter(not_removed, map(_filter_tree, tree)))

	filtered = _filter_tree(tree)
	if filtered is _REMOVED:
		return None
	return filtered


def tree_equal(u, v, eq=lambda u, v: u == v):
	#from jim.debug import debug
	#debug(f"tree_equal: eq({u=!s}, {v=!s})={eq(u,v)}")
	if eq(u, v):
		return True

	is_u_leaf = is_leaf(u)
	is_v_leaf = is_leaf(v)

	if is_u_leaf != is_v_leaf:
		return False
	if is_u_leaf:  # Both leaves, but already not equal.
		return False

	try:
		return all(tree_equal(x, y, eq) for x, y in zip(u, v, strict=True))
	except ValueError:
		return False


def is_mutable(form):
	"""A form is considered mutable if any part of it could be mutated."""
#	if isinstance(form, MutableList):
#		return True
	if is_leaf(form):
		return False
	return any(map(is_mutable, form))


__all__ = [
	*(cls.__name__ for cls in [
		LanguageObject, Form,
		Atom, Bool, Integer, Symbol, String, Execution, UnknownValue,
		List, #MutableList,
		Comment]),
	"nil", "true", "false"]
