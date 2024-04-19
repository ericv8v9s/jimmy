from contextlib import contextmanager
from functools import partial
from pydantic.dataclasses import dataclass

import jim.checker.builtins as jbuiltins
import jim.checker.execution as jexec
import jim.checker.errors as jerrors
from jim.ast import *
from jim.ast import filter_tree
from jim.debug import debug


# Stackframe vs. ProofLevel:
# The call stack is an interpreter internal concept.
# It is only for the implementation of inference rules as executions.
# Proof level is a proof system concept.
# It keeps track of known results and so on,
# and exists in parallel to the stack.


class Stackframe:
	def __init__(self, last_frame, call_form, proof_level=None):
		self.last_frame = last_frame
		self.call_form = call_form
		if proof_level is None:
			proof_level = last_frame.proof_level
		self.proof_level = proof_level
		self.symbol_table = dict()

	def lookup(self, symbol):
		try:
			return self.symbol_table[symbol]
		except KeyError as e:
			if self.last_frame is not None:
				return self.last_frame.lookup(symbol)
			raise UndefinedVariableError(symbol) from e

	def __getitem__(self, key):
		return self.symbol_table[key]


def iter_stack():
	f = top_frame
	while f is not None:
		yield f
		f = f.last_frame


@contextmanager
def push_new_frame(call_form):
	debug(f"PUSH: {call_form}")
	global top_frame
	top_frame = Stackframe(top_frame, call_form)
	try:
		yield top_frame
	except:
		raise
	finally:
		top_frame = top_frame.last_frame
		debug(f"POP: {call_form}")


@contextmanager
def switch_stack(new_top_frame):
	global top_frame
	saved = top_frame
	top_frame = new_top_frame
	try:
		yield new_top_frame
	except:
		raise
	finally:
		top_frame = saved


# Each proof exists in a proof level,
# and each sub-proof gets a new proof level on top of the previous.
class ProofLevel:
	@dataclass(config=dict(arbitrary_types_allowed=True))
	class Result:
		formula: Form
		name: str = None
		assumed: bool = False  # prbly necessary if we add quantifiers

	def __init__(self, previous_level):
		self.previous = previous_level
		self.results: list[Result] = []
		self.assumptions = []
		self.last_form = None

	def copy(self):
		previous = self.previous
		if previous is not None:
			previous = previous.copy()
		cp = ProofLevel(previous)
		cp.results = self.results[:]
		cp.assumptions = self.assumptions[:]
		cp.last_form = self.last_form
		return cp

	def introduce_assumptions(self, *assumptions):
		if self.last_form is not None:
			raise jerrors.JimmyError(top_frame.call_form,
					"Assumption must be introduced at start of proof.")
		for assumption in assumptions:
			debug(f"ASSUMPTION INTR.: {assumption=}")
			self.assumptions.append(assumption)
			self.results.append(ProofLevel.Result(assumption, assumed=True))

	def known_results(self):
		level = self
		while True:
			for result in reversed(level.results):
				yield result
			level = level.previous
			if level is None:
				break

	def lookup(self, key, to_key):
		"""
		Checks all previous results mapped by to_key for equality against key.
		"""
		for result in self.known_results():
			if key == to_key(result):
				return result
		raise KeyError

	def lookup_name(self, name):
		"""Looks up a named result."""
		try:
			return self.lookup(name, lambda r: r.name)
		except KeyError:
			raise UnknownNamedResultError(name) from None

	def is_known(self, formula):
		"""Looks up the formula among known results."""
		try:
			self.lookup(formula, lambda r: r.formula)
			return True
		except KeyError:
			return False

	def is_proven(self, formula):
		for r in self.known_results():
			if r.assumed:
				continue
			if r.formula == formula:
				return True
		return False

	def invalidate(self, critera):
		level = self
		while True:
			level.results = [r for r in level.results if not critera(r)]
			level = level.previous
			if level is None:
				break

	def add_result(self, validated_form):
		result = ProofLevel.Result(validated_form)
		self.results.append(result)

	def mark_last_result(self, name):
		last_result = self.results[-1]
		result = ProofLevel.Result(last_result.formula, name, last_result.assumed)
		self.results[-1] = result


_LAST_LEVEL = object()

@contextmanager
def push_proof_level(based_on=_LAST_LEVEL):
	if based_on is _LAST_LEVEL:
		based_on = top_frame.proof_level
	old = top_frame.proof_level
	top_frame.proof_level = ProofLevel(based_on)
	try:
		yield top_frame.proof_level
	except:
		raise
	finally:
		top_frame.proof_level = old


def init_frame_builtins(frame):
	frame.symbol_table.update(jbuiltins.symbol_table)

top_frame = Stackframe(None, "base frame", ProofLevel(None))
init_frame_builtins(top_frame)


import sys

def show_proof_state(frame=None, title=""):
	if frame is None:
		frame = top_frame
	to_stderr = partial(print, file=sys.stderr)
	to_stderr(format(title, "=^60"))
	to_stderr("| FORMULA                                | NAME        |AS?|")
	for result in frame.proof_level.known_results():
		formula = result.formula
		name = "" if result.name is None else result.name
		assumed = " X " if result.assumed else "   "
		to_stderr(f"| {result.formula!s:<39}| {name:<12}|{assumed}|")
	to_stderr(60 * "=")


def top_level_evaluate(form):
	debug(f"top_level_evaluate( {form} )")

	# purge comments
	form = filter_tree(form, lambda f: not isinstance(f, Comment))
	if form is None:
		return

	evaluate(form)
	if not isinstance(form, ProofAnnotation):
		top_frame.proof_level.last_form = form


def evaluate(obj):
	debug(f"evaluate( {obj} )")

	match obj:
		case Integer(value=v):
			return v
		case Symbol(value=name):
			return top_frame.proof_level.lookup_name(name).formula
		case String(value=s):
			return s

		case ProofAnnotation(children=forms):
			if len(forms) == 0:
				return None
			return invoke(obj)

		case CompoundForm(children=[Symbol(value="progn"), *body]):
			# Special case for progn, always evaluated.
			# TODO The proper way to handle progn should be a sub-proof.
			for form in body:
				evaluate(form)

		case _:
			# Consider it to be a raw object already evaluated (or AST as is).
			return obj


def invoke(compound):
	execution = compound[0]
	match execution:
		case ProofAnnotation():
			execution = evaluate(execution)
		case Symbol(value=name):
			# We lookup in the stack instead of the proof
			# since we are looking for an execution here.
			execution = top_frame.lookup(name)
		case _:
			pass

	argv = compound[1:]

	if not isinstance(execution, jexec.Execution):
		raise jerrors.JimmyError(compound, "Invocation target is invalid.")

	if isinstance(execution, jexec.EvaluateIn):
		argv = [evaluate(arg) for arg in argv]

	debug(f"invoke: {execution} {argv}")

	try:
		matched_params = jexec.fill_parameters(execution.parameter_spec, argv)
	except jexec.ArgumentMismatchError:
		raise ArgumentMismatchError(compound) from None

	with push_new_frame(compound) as f:
		f.symbol_table.update(matched_params)
		result = execution.evaluate(f)

	if isinstance(execution, jexec.EvaluateOut):
		return evaluate(result)
	else:
		return result
