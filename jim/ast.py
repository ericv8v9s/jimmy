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
		return f"{type(self).__name__}({self.value!r})"

	def __str__(self):
		return str(self.value)


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
	pass

class String(Atom):
	_str_escape = str.maketrans({
		'"': '\\"',
		"\\": "\\\\"})
	def __str__(self):
		return '"' + self.value.translate(_str_escape) + '"'


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
