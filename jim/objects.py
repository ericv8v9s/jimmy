from collections import UserList
from abc import ABC, abstractmethod


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


class LanguageObject(ABC):
	@abstractmethod
	def __hash__(self):
		pass

	@abstractmethod
	def __eq__(self):
		pass


class Form(LanguageObject):
	"""Notably, comments are language objects but are not forms."""
	pass

class Atom(_ValueMixin, Form):
	def __init__(self, value):
		super().__init__(value=value)

class _Nil(Form):
	"""Special singleton nil object."""
	def __repr__(self):
		return "nil"
	def __hash__(self):
		return 0
	def __eq__(self, other):
		return self is other
nil = _Nil()

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


class List(list, Form):
	def __init__(self, elements=None):
		list.__init__(self, [] if elements is None else elements)
		LanguageObject.__init__(self)
		self.elements = self  # to make this work with match statements
	def __repr__(self):
		return '(' + " ".join(map(repr, self)) + ')'
	def __str__(self):
		return repr(self)

class MutableList(List):
	def __init__(self, elements=None):
		super().__init__(elements)


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
	if isinstance(form, MutableList):
		return True
	if is_leaf(form):
		return False
	return any(map(is_mutable, form))


__all__ = [x.__name__ for x in [
	LanguageObject, Form,
	Atom, Integer, Symbol, String,
	List, MutableList,
	Comment
]]
__all__.append("nil")
