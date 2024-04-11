from functools import wraps
from jim.ast import *
import jim.grammar as grammar
from jim.checker.errors import *
from jim.checker.execution import Execution
import jim.checker.interpreter as interpreter


symbol_table = dict()


class _InferenceRule(Execution):
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


_ANY_FORM = object()
def rule_of_inference(name, following=_ANY_FORM):
	"""
	Decorates a function to become a rule of inference.
	The function should accept a Stackframe object and an ast object,
	and return a boolean to indicate successful or failed application.
	"""
	def reg_rule(func):
		if following is _ANY_FORM:
			symbol_table[name] = _InferenceRule(func)
			return symbol_table[name]

		# otherwise, rule can only apply following the correct form
		@wraps(func)
		def wrap(frame, proposition):
			if following.check(frame.proof_level.last_form):
				return func(frame, proposition)
			else:
				raise RuleFormMismatchError(
						frame.call_form, frame.proof_level.last_form)
		symbol_table[name] = _InferenceRule(wrap)
		return symbol_table[name]
	return reg_rule


@rule_of_inference("assert", following=grammar.assertion)
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
		return CompoundForm([_substitute(a, b, n) for n in tree])
	except TypeError:  # tree not iterable; it's a leaf
		return tree


# Substitution is a "meta-rule".
# The result of [sub (= a b) y] is a rule that
# replaces all appearances of a to b in y.
class Substitution(Execution):
	# check for (= a b)
	equality_grammar = grammar.compound(
			grammar.symbol("="), grammar.form, grammar.form)

	def __init__(self):
		super().__init__(["equality", "origin"])

	def evaluate(self, frame):
		equality, origin = (
			frame["equality"],
			interpreter.evaluate(frame["origin"]))

		if not Substitution.equality_grammar.check(equality):
			raise JimmyError(equality, "Form must be a two-term equality.")

		a, b = equality[1], equality[2]
		expected = _substitute(a, b, origin)
		return _InferenceRule(lambda f, ast: expected == ast)()

symbol_table["sub"] = Substitution()


@rule_of_inference("assign", following=grammar.assignment)
def assignment(frame, ast):
	last_form = frame.proof_level.last_form
	lhs, rhs = last_form[1], last_form[2]

	# Application is valid if the substitution result was already proven.
	target = _substitute(lhs, rhs, ast)
	level = frame.proof_level
	while level is not None:
		for result in level.results:
			if target == result.formula:
				break
		level = level.previous
	else:
		# All results from all levels checked; no match.
		return False

	# Assignment must also invalidate all previous results
	# that involve the symbol being assigned to.
	level = frame.proof_level
	while level is not None:
		level.results = [r for r in level.results if lhs not in r.formula]
		level = level.previous

	return True


# Handled as a special case by the interpreter.
#@rule_of_inference("progn", following=grammar.progn)
#def progn(frame, ast):
#	pass


@rule_of_inference("cond", following=grammar.conditional)
def conditional(frame, ast):
	# TODO
	raise NotImplementedError


class Conditional(jexec.Macro):
	def __init__(self):
		# (cond
		#   ((test1) things...)
		#   ((test2) things...))
		super().__init__([["branches"]])

	def evaluate(self, frame):
		for b in frame["branches"]:
			match b:
				case CompoundForm(children=[test, *body]):
					with interpreter.switch_stack(frame.last_frame):
						if _truthy(interpreter.evaluate(test)):
							return _wrap_progn(body)
				case _:
					raise errors.SyntaxError(b, "Invalid conditional branch.")
		return nil


@rule_of_inference("while", following=grammar.while_loop)
def while_loop(frame, ast):
	while_form = frame.proof_level.last_form
	loop_cond = while_form[1]

	with interpreter.push_new_proof_level() as pl:
		pl.add_result(loop_cond, assumed=True)
		for form in while_form.children[2:]:
			interpreter.evaluate(form)

		# check last result for the invariant
		invar = pl.results[-1]
		try:
			pl.previous.lookup(invar, lambda r: r.formula)
		except KeyError:
			raise JimmyError(invar, "Invariant not established before loop.")

	return ast == CompoundForm([Symbol("and"),
			CompoundForm([Symbol("not"), loop_cond]),
			invar])


class Addition(jexec.Function):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		terms = frame["terms"]
		_require_ints(terms)
		return sum(terms)


class Subtraction(jexec.Function):
	def __init__(self):
		super().__init__(["n", ["terms"]])
	def evaluate(self, frame):
		n = frame["n"]
		terms = frame["terms"]
		_require_ints(terms + [n])

		if len(terms) == 0:
			return -n
		return n - sum(terms)


class Multiplication(jexec.Function):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		terms = frame["terms"]
		_require_ints(terms)
		return product(terms)


class Division(jexec.Function):
	def __init__(self):
		super().__init__(["n", ["terms"]])
	def evaluate(self, frame):
		n = frame["n"]
		terms = frame["terms"]
		_require_ints(terms + [n])

		try:
			if len(terms) == 0:
				return 1 // n
			return n // product(terms)
		except ZeroDivisionError:
			raise errors.DivideByZeroError(frame.call_form)


class Modulo(jexec.Function):
	def __init__(self):
		super().__init__(["x", "y"])
	def evaluate(self, frame):
		x, y = frame["x"], frame["y"]
		_require_ints([x, y])
		if y == 0:
			raise errors.DivideByZeroError(frame.call_form)
		return x % y


def _chain_relation(relation_pred, a, b, more):
		result = relation_pred(a, b)
		for t in more:
			if not result:
				break
			a = b
			b = t
			result = relation_pred(a, b)
		return result


class Equality(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a == b, frame["a"], frame["b"], frame["more"])


class LessThan(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a < b, frame["a"], frame["b"], frame["more"])


class GreaterThan(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a > b, frame["a"], frame["b"], frame["more"])


class LessEqual(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a <= b, frame["a"], frame["b"], frame["more"])


class GreaterEqual(jexec.Function):
	def __init__(self):
		super().__init__(["a", "b", ["more"]])
	def evaluate(self, frame):
		return _chain_relation(
			lambda a, b: a >= b, frame["a"], frame["b"], frame["more"])


# Empty conjunction is vacuously true.
class Conjunction(jexec.Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		result = True
		for t in frame["terms"]:
			with interpreter.switch_stack(frame.last_frame):
				result = interpreter.evaluate(t)
				if not _truthy(result):
					return False
		return result


# Empty disjunction is vacuously false.
# (or ...) is true iff any argument is true;
# an empty (or) has no argument which is true.
class Disjunction(jexec.Execution):
	def __init__(self):
		super().__init__([["terms"]])
	def evaluate(self, frame):
		for t in frame["terms"]:
			with interpreter.switch_stack(frame.last_frame):
				result = interpreter.evaluate(t)
				if _truthy(result):
					return result
		return False


class Negation(jexec.Function):
	def __init__(self):
		super().__init__(["p"])
	def evaluate(self, frame):
		return not _truthy(frame["p"])


class Print(jexec.Function):
	def __init__(self):
		super().__init__(["msg"])
	def evaluate(self, frame):
		print(frame["msg"])
		return nil


def _preorder_walk(tree, visitor=lambda x: x, leaves_only=False):
	"""
	Walks the tree in pre-order and visits each node using the visitor.
	The tree should be structured as nested iterables.
	"""

	stack = []

	try:
		stack.append(iter(tree))
		if not leaves_only:
			yield visitor(tree)
	except TypeError:
		yield visitor(tree)

	while len(stack) > 0:
		try:
			n = next(stack[-1])
		except StopIteration:
			stack.pop()
			continue

		try:
			stack.append(iter(n))
			if not leaves_only:
				yield visitor(n)
		except TypeError:
			yield visitor(n)
