from abc import ABC, abstractmethod
from jim.ast import *
from jim.debug import debug


class _GrammarComponent(ABC):
	def __init__(self):
		super().__init__()
		self.specialization = None

	@abstractmethod
	def check(self, ast: CodeObject):
		raise NotImplementedError

	def specialize(self, specialization):
		"""
		Decorate with a specialization function such that when the resulting
		component is called, a new component that matches against the
		specialization is returned.
		"""
		self.specialization = specialization
		return self

		# This member function is used to decorate another function,
		# which is used to specialize this grammar component.
		# The return value of this function is an instance from a dynamically
		# created class: it is still a grammar component with the same
		# functionalities, except the object is now a callable.
		# Calling the object calls make_spec_component, which stores the arguments
		# as specialization specification and produces a new component that uses
		# the decorated function for validation.

		def make_spec_component(self, *args, **kws):
			return _SpecializedComponent(self, specialization, args, kws)

		# dynamically creates a new class
		return type(
			specialization.__name__,
			(_GrammarComponent,),
			dict(__call__=make_spec_component))()

	def __call__(self, *args):
		if self.specialization:

	def __or__(self, other):
		return _grammar_component(
			lambda ast: self.check(ast) or other.check(ast))

	def __and__(self, other):
		return _grammar_component(
			lambda ast: self.check(ast) and other.check(ast))


class _PredicateComponent(_GrammarComponent):
	def __init__(self, check_func):
		self.check_func = check_func
	def check(self, ast):
		return self.check_func(ast)
	def __repr__(self):
		return self.check_func.__name__


class _SpecializedComponent(_GrammarComponent):
	def __init__(self, spec, args, kws):
		self.spec = spec
		self.args = args
		self.kws = kws

	def check(self, ast):
		debug("GRAMMAR:", f"{self.origin}({self.args} {self.kws})")
		out = self.origin.check(ast) and self.spec(ast, *self.args, **self.kws)
		debug("GRAMMAR", "ACCEPT" if out else "REJECT")
		return out

	def __repr__(self):
		return f"{self.spec.__name__}({self.args} {self.kws})"


class repeat(_GrammarComponent):
	def __init__(self, component):
		self.component = component
	def check(self, ast):
		return True
	def __repr__(self):
		return f"repeat({repr(self.component)})"


def _grammar_component(check_func):
	return _PredicateComponent(check_func)


@_grammar_component
def symbol(ast):
	return isinstance(ast, Symbol)

@symbol.specialize
def symbol(ast, name):
	return ast.value == name

@_grammar_component
def form(ast):
	return isinstance(ast, Form)


@_grammar_component
def compound(ast):
	return isinstance(ast, CompoundForm)

@compound.specialize
def compound(ast, *forms_spec):
	if len(forms_spec) == 0:
		return len(ast) == 0

	idx = 0
	for s in forms_spec:
		debug(s)
		if isinstance(s, repeat):
			while idx < len(ast) and s.component.check(ast[idx]):
				idx += 1
		else:
			if idx >= len(ast) or not s.check(ast[idx]):
				return False
			idx += 1
	return idx == len(ast) - 1


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
