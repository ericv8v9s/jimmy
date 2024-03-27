class ValueMixin:
	def __init__(self, value, *args, **kws):
		self.value = value
		super().__init__(*args, **kws)

	def __str__(self):
		return str(self.value)

	def __hash__(self):
		return hash(self.value)


class CompoundMixin:
	def __init__(self, children, *args, **kws):
		self.children = tuple(children)
		super().__init__(*args, **kws)

	def __getitem__(self, key):
		return self.children[key]

	def __hash__(self):
		return hash(self.children)


class CodeObject:
	pass

class Form(CodeObject):
	pass

class Atom(ValueMixin, Form):
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
		return '"' + self.value.translate(self._str_escape) + '"'


class CompoundForm(CompoundMixin, Form):
	def __init__(self, forms):
		super().__init__(children=forms)
	def __str__(self):
		return "(" + " ".join(map(str, self.children)) + ")"


class ProofAnnotation(CompoundMixin, CodeObject):
	def __init__(self, forms):
		super().__init__(children=forms)
	def __str__(self):
		return "[" + " ".join(map(str, self.children)) + "]"


class Comment(ValueMixin, CodeObject):
	def __init__(self, content):
		super().__init__(value=content)
	def __str__(self):
		return f";{self.value}\n"
