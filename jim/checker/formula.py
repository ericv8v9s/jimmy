from jim.syntax import *


def require_compound_type(form, head):
	try:
		assert isinstance(form[0], Symbol) and form[0].value == head
	except:
		raise RuntimeError(f"{form} is not a '{head}' form.")


_specializations = dict()

def specialization_of(compound_head):
	def add_specialization(cls):
		_specializations[compound_head] = cls
		return cls
	return add_specialization

def specialize(form):
	if type(form) != CompoundForm:
		return form
	return _specializations.get(form.children[0], lambda x: x)(form)


@specialization_of("and")
class Conjunction(CompoundForm):
	def __init__(form: CompoundForm):
		super().__init__(self, form.children)
		self.conjuncts = set(map(specialize, self.children[1:]))


@specialization_of("or")
class Disjunction(CompoundForm):
	def __init__(form: CompoundForm):
		super().__init__(self, form.children)
		self.disjuncts = set(map(specialize, form.children[1:]))


