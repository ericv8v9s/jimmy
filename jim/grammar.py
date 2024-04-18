from abc import ABC, abstractmethod
from jim.ast import *
from jim.debug import debug


class _GrammarBase(ABC):
	@abstractmethod
	def check(self, ast: CodeObject):
		raise NotImplementedError


class _grammar(_GrammarBase):
	def __init__(self, check_func,
			spec_check=None, specification=None):
		self.check_func = check_func
		# Specification for specialization:
		# an iterable of other grammars components.
		self.specification = specification
		self.spec_check = spec_check if spec_check else check_func

	def check(self, ast: CodeObject):
		if self.specification is None:
			return self.check_func(ast)
		return self.check_func(ast) and self.spec_check(ast, *self.specification)

	def specialized(self, specialized_check):
		return _grammar(
				self.check_func,
				spec_check=specialized_check,
				specification=self.specification)

	def __call__(self, *specification):
		"""Produces a new grammar object that checks against the specification."""
		return _grammar(
				self.check_func,
				spec_check=self.spec_check,
				specification=specification)

	def __repr__(self):
		if self.specification is None:
			return self.check_func.__name__
		return self.spec_check.__name__   \
				+ "(" + " ".join(map(repr, self.specification)) + ")"


class repeat(_GrammarBase):
	def __init__(self, component):
		self.component = component
	def check(self, ast):
		return True
	def __repr__(self):
		return f"repeat({self.component!r})"


@_grammar
def symbol(ast):
	return isinstance(ast, Symbol)

@symbol.specialized
def symbol(ast, name):
	return ast.value == name


@_grammar
def form(ast):
	return isinstance(ast, Form)


@_grammar
def compound(ast):
	return isinstance(ast, CompoundForm)

@compound.specialized
def compound(ast, *children):
	idx = 0
	for s in children:
		debug(f"GRAMMAR: {s!r} == {ast[idx]!r}")
		if isinstance(s, repeat):
			while idx < len(ast) and s.component.check(ast[idx]):
				idx += 1
		else:
			if idx >= len(ast) or not s.check(ast[idx]):
				return False
			idx += 1
	return idx == len(ast)


assertion = compound(symbol("assert"), form)
assignment = compound(symbol("assign"), symbol, form)
function = compound(symbol("func"), compound, repeat(form))
progn = compound(symbol("progn"), repeat(form))
conditional = compound(symbol("cond"), repeat(compound(form, repeat(form))))
implication = compound(symbol("imply"), form, form)
while_loop = compound(symbol("while"), form, repeat(form))
equality = compound(symbol("="), form, form)
conjunction = compound(symbol("and"), repeat(form))
disjunction = compound(symbol("or"), repeat(form))
addition = compound(symbol("+"), repeat(form))
subtraction = compound(symbol("-"), form, repeat(form))
multiplication = compound(symbol("*"), repeat(form))
division = compound(symbol("/"), form, repeat(form))
