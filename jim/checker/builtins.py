from functools import wraps, partial
from itertools import filterfalse
from collections import Counter

import jim.ast
from jim.ast import *
import jim.grammar as gmr
from jim.grammar import symbol, compound, repeat, form
from jim.checker.execution import Execution, Function
import jim.checker.interpreter as interpreter
import jim.checker.errors as jerrors
from jim.debug import debug


symbol_table = dict()


class _InferenceRule(Function):
	def __init__(self, validation_func):
		super().__init__(["_"])
		self.validation_func = validation_func

	def evaluate(self, frame):
		with interpreter.switch_stack(frame.last_frame) as f:
			valid = self.validation_func(f, frame["_"])
			assert isinstance(valid, bool)
			if not valid:
				raise jerrors.InvalidRuleApplicationError(frame.call_form)
			frame.proof_level.add_result(frame["_"])
		return frame["_"]

	def __repr__(self):
		return f"{type(self).__name__}({self.validation_func.__name__})"


_ANY_FORM = object()
def rule_of_inference(name, following=_ANY_FORM):
	"""
	Decorates a function to become a rule of inference.
	The function should accept a Stackframe object and an ast object,
	and return a boolean to indicate successful or failed application.
	"""
	debug(
			f"REGISTER RULE: {'anon.' if name is None else name} "
			f"following {'any' if following is _ANY_FORM else repr(following)}")

	def make_rule(func):
		if following is _ANY_FORM:
			return _InferenceRule(func)

		# otherwise, rule can only apply following the correct form
		@wraps(func)
		def wrap(frame, proposition):
			debug(
				f"GRAMMAR: {following!r}"
				f" == {frame.proof_level.last_form!r}")
			grammar_match = following.check(frame.proof_level.last_form)
			debug("GRAMMAR:", "ACCEPT" if grammar_match else "REJECT")
			if grammar_match:
				return func(frame, proposition)
			else:
				raise jerrors.RuleFormMismatchError(
						frame.call_form, frame.proof_level.last_form)
		return _InferenceRule(wrap)

	if name is not None:
		def reg_rule(func):
			symbol_table[name] = make_rule(func)
			return symbol_table[name]
		return reg_rule
	else:
		return lambda f: make_rule(f)


# Not really a rule of inference.
# Marks the last result with a name, allowing it to be referenced later.
# This is a special execution that doesn't contribute to
# the correctness of the proof (the result can simply be reiterated),
# but only serves to make it less tedious.
class MarkResult(Execution):
	def __init__(self):
		super().__init__(["name"])
	def evaluate(self, frame):
		name = frame["name"].value
		frame.proof_level.mark_last_result(frame["name"].value)

symbol_table["mark"] = MarkResult()


class ShowProofState(Execution):
	def __init__(self):
		super().__init__(["id"])

	def evaluate(self, frame):
		interpreter.show_proof_state(frame, f" Known results: {frame['id']} ")

symbol_table["show_proof_state"] = ShowProofState()


class AssumptionIntroduction(Function):
	def __init__(self):
		super().__init__(["assumption"])

	def evaluate(self, frame):
		assumption = frame["assumption"]
		pl = frame.proof_level

		if pl.last_form is not None:
			raise jerrors.RuleFormMismatchError(
					frame.call_form, pl.last_form,
					"Rule must be applied at start of proof or sub-proof.")

		frame.proof_level.introduce_assumptions(assumption)
		return assumption

symbol_table["assume"] = AssumptionIntroduction()


@rule_of_inference("assert", following=gmr.assertion)
def assertion(frame, ast):
	return frame.proof_level.last_form[1] == ast


# Substitution is a "meta-rule".
# The result of [sub (= a b) y] is a rule that
# accepts any replacements of a to b in y.
class Substitution(Function):
	def __init__(self):
		super().__init__(["equality", "origin"])

	def evaluate(self, frame):
		equality, origin = frame["equality"], frame["origin"]

		if not gmr.equality.check(equality):
			raise jerrors.JimmyError(equality, "Form must be a two-term equality.")

		a, b = equality[1], equality[2]
		@rule_of_inference(None)
		def sub_rule(f, ast):
			debug(f"RULE sub {a}->{b}: {origin=!s}; {ast=!s}")
			return jim.ast.tree_equal(origin, ast,
					lambda u, v: u == v or (u == a and v == b))
		return sub_rule

symbol_table["sub"] = Substitution()


def _substitute(a, b, tree):
	"""
	Substitutes all occurrences of a to b in tree,
	where a and b can by any form (compound form would substitute a sub-tree).
	"""
	if tree == a:
		return b
	try:
		# Yes, this is grossly inefficient.
		return CompoundForm([_substitute(a, b, n) for n in tree])
	except TypeError:  # tree not iterable; it's a leaf
		return tree

@rule_of_inference("assign", following=gmr.assignment)
def assignment(frame, ast):
	last_form = frame.proof_level.last_form
	lhs, rhs = last_form[1], last_form[2]

	# Application is valid if the substitution result was already proven.
	target = _substitute(lhs, rhs, ast)
	debug(f"RULE assign: need {target}")

	level = frame.proof_level
	if not level.is_known(target):
		return False

	# Assignment must also invalidate all previous results that involve
	# the symbol being assigned to.
	while level is not None:
		level.results = [r for r in level.results if lhs not in r.formula]
		level = level.previous

	return True


# Handled as a special case by the interpreter.
#@rule_of_inference("progn", following=gmr.progn)
#def progn(frame, ast):
#	pass


@rule_of_inference("cond", following=gmr.conditional)
def conditional(frame, ast):
	# TODO
	raise NotImplementedError


@rule_of_inference("while", following=gmr.while_loop)
def while_loop(frame, ast):
	while_form = frame.proof_level.last_form
	loop_cond = while_form[1]

	proof_copy = frame.proof_level.copy()
	with interpreter.push_proof_level() as pl:
		pl.introduce_assumptions(loop_cond)
		for form in while_form.children[2:]:
			interpreter.top_level_evaluate(form)

		# We expect to find at least two assumptions:
		# one is the loop condition, the rest makes the loop invariant.
		invar = list(filter(lambda a: a != loop_cond, pl.assumptions))
		if len(invar) == 1:
			invar = invar[0]
		else:
			invar = CompoundForm(Symbol("and"), *invar)

		debug(f"while: expected invar.: {invar!s}")

		# Ensure invariant maintained within loop.
		if not pl.is_known(invar):
			raise jerrors.JimmyError(invar, "Invariant not maintained.")

	# Ensure invariant known before loop.
	if not proof_copy.is_known(invar):
		raise jerrors.JimmyError(invar, "Invariant not established before loop.")

	return ast == CompoundForm([Symbol("and"),
			CompoundForm([Symbol("not"), loop_cond]),
			invar])


def _match_formula(actual, *expected):
	"""
	Checks that the provided formula and expectation shares the same prefix.
	"""
	debug("match formula: "
		f"expecting {' '.join(map(repr, expected))}; "
		f"actual {' '.join(map(repr, actual))}")
	return all(actual[i] == x for i, x in enumerate(expected))


def _equality_relation(relation_spec):
	"""
	Wraps a rule of inference definition with an equality form check
	and directly provides the lhs and rhs instead of the ast.
	"""
	# A lot of rules take the form of [xxx (= lhs (op x y z ...))]
	@wraps(relation_spec)
	def wrap(frame, ast):
		return gmr.equality.check(ast) and relation_spec(frame, ast[1], ast[2])
	return wrap


@rule_of_inference("=intr")
@_equality_relation
def identity_introduction(frame, lhs, rhs):
	return lhs == rhs

@rule_of_inference("=flip")
@_equality_relation
def equality_flip(frame, lhs, rhs):
	return frame.proof_level.is_known(CompoundForm([Symbol("="), rhs, lhs]))


@rule_of_inference("conj-intr")
def conjunction_introduction(frame, ast):
	# If all conjunts are proven.
	if not gmr.conjunction.check(ast):
		return False
	for formula in ast.children[1:]:
		if not frame.proof_level.is_known(formula):
			raise jerrors.JimmyError(formula, "Conjunt not known.")
	return True


@rule_of_inference("conj-elim")
def conjunction_elimination(frame, ast):
	# If ast is found in a proven conjunction.
	known_results = frame.proof_level.known_results()
	for formula in map(lambda r: r.formula, known_results):
		match formula:
			case CompoundForm(children=[Symbol("and"), *conjunts]):
				if ast in conjunts:
					return True
	return False


@rule_of_inference("disj-intr")
def disjunction_introduction(frame, ast):
	if not gmr.disjunction.check(ast):
		return False
	for formula in ast.children[1:]:
		if frame.proof_level.is_known(formula):
			return True
	return False


# TODO disjunction elimination
# This is pain. It goes like this:
# [[disj-elim (or a b c ...) (a->z) (b->z) (c->z) ...] z]
# We basically have to prove the conclusion z from each disjunct.


# TODO conditional introduction
# Probably will need an associated execution for introducing a sub-proof.


class ModusPonens(Function):
	def __init__(self):
		super().__init__(["_"])

	def evaluate(self, frame):
		implication = frame["_"]
		if not gmr.implication.check(implication):
			raise jerrors.JimmyError(implication, "Not an implication.")
		p, q = implication[1], implication[2]
		def rule_spec(f, ast):
			is_known = f.proof_level.is_known
			return is_known(implication) and is_known(p) and ast == q
		return rule_of_inference(None)(rule_spec)

symbol_table["mp"] = ModusPonens()


# TODO contradition stuff


# TODO Arithmetic rules should be properly built from Peano axioms.
# Some of those can definitely be turned into theorems.

@rule_of_inference("add0")
@_equality_relation
def additive_identity(f, lhs, rhs):
	debug(f"{lhs=}; {rhs=}")
	return rhs == CompoundForm([Symbol("+"), Integer(0), lhs])  \
			or rhs == CompoundForm([Symbol("+"), lhs, Integer(0)])  \
			or rhs == CompoundForm([Symbol("+"), lhs])  \
			or rhs == CompoundForm([Symbol("+")])

@rule_of_inference("subt0")
@_equality_relation
def subtractive_identity(f, lhs, rhs):
	# [subt0 (= x (- x 0))]
	return rhs == CompoundForm([Symbol("-"), lhs, Integer(0)])


@rule_of_inference("subt0")
@_equality_relation
def subtractive_identity(f, lhs, rhs):
	# [subt0 (= 0 (- x x))]
	debug(f"{lhs=}; {rhs=}")
	return lhs == Integer(0)  \
			and compound(symbol("-"), form, form).check(rhs)  \
			and rhs[1] == rhs[2]


@rule_of_inference("mult0")
@_equality_relation
def multiply_zero(f, lhs, rhs):
	# [mult0 (= 0 (* 0 anything...))]
	debug(f"{lhs=}; {rhs=}")
	return lhs == Integer(0) and any(map(lambda f: f == Integer(0), rhs.rest))


@rule_of_inference("mult1")
@_equality_relation
def multiplicative_identity(f, lhs, rhs):
	debug(f"{lhs=}; {rhs=}")
	return rhs == CompoundForm([Symbol("*"), Integer(1), lhs])  \
			or rhs == CompoundForm([Symbol("*"), lhs, Integer(1)])  \
			or rhs == CompoundForm([Symbol("*"), lhs])

@rule_of_inference("+comm")
@_equality_relation
def addition_commutativity(f, lhs, rhs):
	return Symbol("+") == lhs.head == rhs.head  \
			and Counter(lhs.rest) == Counter(rhs.rest)

@rule_of_inference("*comm")
@_equality_relation
def multiplication_commutativity(f, lhs, rhs):
	return Symbol("*") == lhs.head == rhs.head  \
			and Counter(lhs.rest) == Counter(rhs.rest)


def _tree_flatten1(tree):
	"""
	For every child of the root, if it shares the same first child as root,
	all the remaining children (grand-children of root) are brought up to become
	children of root.
	"""
	try:
		children = iter(tree)
		first_child = next(children)
	except (TypeError, StopIteration):
		return tree, 0

	flattened = [first_child]
	flattens = 0
	for child in children:
		try:
			grand_children = iter(child)
			first_gc = next(grand_children)
		except (TypeError, StopIteration):
			flattened.append(child)
			continue

		if first_gc == first_child:
			flattens += 1
			for gc in grand_children:
				flattened.append(gc)
	return flattened, flattens

def _tree_flatten(tree):
	tree, flattens = _tree_flatten1(tree)
	while flattens != 0:
		tree, flattens = _tree_flatten1(tree)
	return tree


@rule_of_inference("+assoc")
@_equality_relation
def addition_associativity(f, lhs, rhs):
	if not gmr.addition.check(lhs):
		return False
	return _tree_flatten(lhs) == _tree_flatten(rhs)

@rule_of_inference("*assoc")
@_equality_relation
def multiplication_associativity(f, lhs, rhs):
	if not gmr.multiplication.check(lhs):
		return False
	return _tree_flatten(lhs) == _tree_flatten(rhs)


@rule_of_inference("*distr")
@_equality_relation
def multiplication_distributivity(f, lhs, rhs):
	# We expect (* x (+ a b c ...)) for lhs;
	# (+ (* x a) (* x b) ...) for rhs.
	# We expect the two to match after pulling common factors out of lhs.
	sym = symbol
	cmp = compound
	lhs_gmr = cmp(sym("*"), form, cmp(sym("+"), repeat(form)))
	rhs_gmr = cmp(sym("+"), repeat(cmp(sym("*"), form, repeat(form))))
	if not (lhs_gmr.check(lhs) and rhs_gmr.check(rhs)):
		return False

	common_factor = lhs[1]
	terms = lhs[2].rest
	expected = CompoundForm([Symbol("+"), *(
			CompoundForm([Symbol("*"), common_factor, term]) for term in terms)])
	return expected == rhs


@rule_of_inference("-+")
@_equality_relation
def subtraction_to_sum(f, lhs, rhs):
	# (= (- a b c ...) (+ a (- b) (- c) ...))
	debug(f"RULE -+: {lhs=}; {rhs=}")
	lhs_gmr = compound(symbol("-"), form, repeat(form))
	rhs_gmr = compound(symbol("+"), form, repeat(compound(symbol("-"), form)))
	if not (lhs_gmr.check(lhs) and rhs_gmr.check(rhs)):
		debug(f"RULE -+: grammar reject")
		return False
	if lhs[1] != rhs[1]:
		debug(f"RULE -+: common factor mismatch")
		return False

	try:
		for l, r in zip(lhs.children[2:], rhs.children[2:], strict=True):
			if r != CompoundForm([Symbol("-"), l]):
				debug(f"RULE -+: {r} != {CompoundForm([Symbol('-'), l])}")
				return False
	except ValueError:
		return False

	return True


# TODO division and mod

