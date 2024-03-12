class CodeObject:
	pass


class Form(CodeObject):
	pass


class Atom(Form):
	def __init__(self, value):
		super().__init__()
		self.value = value
	def __str__(self):
		return str(self.value)

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


class Compound(CodeObject):
	def __init__(self, children):
		super().__init__()
		self.children = children
	def __getitem__(self, key):
		return self.children[key]


class CompoundForm(Compound, Form):
	def __init__(self, forms):
		Compound.__init__(self, forms)
		Form.__init__(self)
	def __str__(self):
		return "(" + " ".join(map(str, self.children)) + ")"


class ProofAnnotation(CodeObject):
	def __init__(self, forms):
		super().__init__()
		self.children = forms
	def __str__(self):
		return "[" + " ".join(map(str, self.children)) + "]"


class Comment(CodeObject):
	def __init__(self, content):
		super().__init__()
		self.value = content
	def __str__(self):
		return f";{self.value}\n"
