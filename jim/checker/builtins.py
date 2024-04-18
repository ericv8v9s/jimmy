from functools import wraps, partial

from jim.ast import *
import jim.grammar as gmr
from jim.checker.errors import *
from jim.checker.execution import Execution, Function
import jim.checker.interpreter as interpreter
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
				raise InvalidRuleApplicationError(frame.call_form)
			frame.proof_level.add_result(frame["_"])

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
				raise RuleFormMismatchError(
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


import sys

class DisplayProofState(Execution):
	def __init__(self):
		super().__init__(["id"])

	def evaluate(self, frame):
		to_stderr = partial(print, file=sys.stderr)
		title = f" Known results: {frame['id']} "

		to_stderr(format(title, "=^60"))
		to_stderr("| FORMULA                                | NAME        |AS?|")
		for result in frame.proof_level.known_results():
			formula = result.formula
			name = "" if result.name is None else result.name
			assumed = " X " if result.assumed else "   "
			to_stderr(f"| {result.formula!s:<39}| {name:<12}|{assumed}|")
		to_stderr(60 * "=")

symbol_table["__show_known"] = DisplayProofState()


@rule_of_inference("assert", following=gmr.assertion)
def assertion(frame, ast):
	return frame.proof_level.last_form[1] == ast


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


# Substitution is a "meta-rule".
# The result of [sub (= a b) y] is a rule that
# replaces all appearances of a to b in y.
class Substitution(Function):
	def __init__(self):
		super().__init__(["equality", "origin"])

	def evaluate(self, frame):
		equality, origin = frame["equality"], frame["origin"]

		if not gmr.equality.check(equality):
			raise JimmyError(equality, "Form must be a two-term equality.")

		a, b = equality[1], equality[2]
		expected = _substitute(a, b, origin)
		return rule_of_inference(None)(lambda f, ast: expected == ast)

symbol_table["sub"] = Substitution()


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


#class Conditional(jexec.Macro):
#	def __init__(self):
#		# (cond
#		#   ((test1) things...)
#		#   ((test2) things...))
#		super().__init__([["branches"]])
#
#	def evaluate(self, frame):
#		for b in frame["branches"]:
#			match b:
#				case CompoundForm(children=[test, *body]):
#					with interpreter.switch_stack(frame.last_frame):
#						if _truthy(interpreter.evaluate(test)):
#							return _wrap_progn(body)
#				case _:
#					raise errors.SyntaxError(b, "Invalid conditional branch.")
#		return nil


@rule_of_inference("while", following=gmr.while_loop)
def while_loop(frame, ast):
	while_form = frame.proof_level.last_form
	loop_cond = while_form[1]

	with interpreter.push_new_proof_level() as pl:
		pl.add_result(loop_cond, assumed=True)
		for form in while_form.children[2:]:
			interpreter.evaluate(form)

		# check last result for the invariant
		invar = pl.results[-1]
		if not pl.previous.is_known(invar):
			raise JimmyError(invar, "Invariant not established before loop.")

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
	return frame.proof_level.is_known(CompoundForm(Symbol("="), rhs, lhs))


@rule_of_inference("conj-intr")
def conjunction_introduction(frame, ast):
	# If all conjunts are proven.
	if not gmr.conjunction.check(ast):
		return False
	for formula in ast.children[1:]:
		if not frame.proof_level.is_known(formula):
			raise JimmyError(formula, "Conjunt not known.")
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
			raise JimmyError(implication, "Not an implication.")
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
	return _match_formula(rhs, Symbol("+"), lhs, Integer(0))

@rule_of_inference("subt0")
@_equality_relation
def subtractive_identity(f, lhs, rhs):
	return _match_formula(rhs, Symbol("-"), lhs, Integer(0))


@rule_of_inference("mult0")
@_equality_relation
def multiply_zero(f, lhs, rhs):
	# expect [0* (= 0 (* 0 anything...))]
	debug(f"{lhs=}")
	debug(f"{rhs=}")
	return lhs == Integer(0) and _match_formula(rhs, Symbol("*"), Integer(0))

@rule_of_inference("mult1")
@_equality_relation
def multiplicative_identity(f, lhs, rhs):
	return _match_formula(rhs, Symbol("*"), lhs, Integer(1))

@rule_of_inference("*wrap")
@_equality_relation
def mult_wrap(f, lhs, rhs):
	return gmr.compound(gmr.symbol("*"), gmr.form).check(rhs) and rhs[1] == lhs

@rule_of_inference("+wrap")
@_equality_relation
def addition_wrap(f, lhs, rhs):
	return gmr.compound(gmr.symbol("+"), gmr.form).check(rhs) and rhs[1] == lhs


def _tree_flatten1(tree):
	"""
	For every child of the root, if it shares the same first child as root,
	all the remaining children (grand-children of root) are brought up to become
	children of root.
	"""
	try:
		children = iter(tree)
		first_child = next(children)
	except TypeError | StopIteration:
		return tree, 0

	flattened = [first_child]
	flattens = 0
	for child in children:
		try:
			grand_children = iter(child)
			first_gc = next(grand_children)
		except TypeError | StopIteration:
			flattened.append(child)

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
	if not gmr.compound(gmr.symbol("*"),
			gmr.form, gmr.form, gmr.repeat(gmr.form)).check(rhs):
		return False
	distributing = rhs[1]
	result = [Symbol("+")]
	for x in rhs.children[1:]:
		distributed.append(CompoundForm([Symbol("*"), ]))


# TODO division and mod


#def _preorder_walk(tree, visitor=lambda x: x, leaves_only=False):
#	"""
#	Walks the tree in pre-order and visits each node using the visitor.
#	The tree should be structured as nested iterables.
#	"""
#
#	stack = []
#
#	try:
#		stack.append(iter(tree))
#		if not leaves_only:
#			yield visitor(tree)
#	except TypeError:
#		yield visitor(tree)
#
#	while len(stack) > 0:
#		try:
#			n = next(stack[-1])
#		except StopIteration:
#			stack.pop()
#			continue
#
#		try:
#			stack.append(iter(n))
#			if not leaves_only:
#				yield visitor(n)
#		except TypeError:
#			yield visitor(n)
