from abc import ABC, abstractmethod
from jim.debug import debug


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
		return f"{type(self).__name__}({self.value!r})"

	def __str__(self):
		return repr(self.value)


class _CompoundMixin:
	def __init__(self, children, *args, **kws):
		self.children = tuple(children)
		super().__init__(*args, **kws)

	def __len__(self):
		return len(self.children)

	def __iter__(self):
		return iter(self.children)

	def __getitem__(self, key):
		return self.children[key]

	def __contains__(self, item):
		return self == item or any(item in child for child in self.children)

	@property
	def head(self):
		return self.children[0]

	@property
	def rest(self):
		return self.children[1:]

	def __repr__(self):
		return type(self).__name__  \
				+ "(" + " ".join(map(repr, self.children)) + ")"

	def __hash__(self):
		return hash(self.children)

	def __eq__(self, other):
		return type(self) is type(other) and self.children == other.children


class CodeObject(ABC):
	@abstractmethod
	def __hash__(self):
		pass

	@abstractmethod
	def __eq__(self):
		pass


class Form(CodeObject):
	pass

class Atom(_ValueMixin, Form):
	def __init__(self, value):
		super().__init__(value=value)

class Integer(Atom):
	pass

class Symbol(Atom):
	def __str__(self):
		return self.value

class String(Atom):
	_str_escape = str.maketrans({
		'"': '\\"',
		"\\": "\\\\"})
	def __str__(self):
		return '"' + self.value.translate(self._str_escape) + '"'


class CompoundForm(_CompoundMixin, Form):
	def __init__(self, forms):
		super().__init__(children=forms)
	def __str__(self):
		return "(" + " ".join(map(str, self.children)) + ")"

class ProofAnnotation(_CompoundMixin, CodeObject):
	def __init__(self, forms):
		super().__init__(children=forms)
	def __str__(self):
		return "[" + " ".join(map(str, self.children)) + "]"

class Comment(_ValueMixin, CodeObject):
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


__all__ = [x.__name__ for x in [
	CodeObject,
	Form,
	Atom, Integer, Symbol, String,
	CompoundForm,
	ProofAnnotation,
	Comment
]]
