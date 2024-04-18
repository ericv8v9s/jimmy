from contextlib import contextmanager
from functools import partial
from pydantic.dataclasses import dataclass

import jim.checker.builtins as jbuiltins
import jim.checker.execution as jexec
from .errors import *
from jim.ast import *
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
		self.last_form = None

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
		try:
			return not self.lookup(formula, lambda r: r.formula).assumed
		except KeyError:
			return False

	def add_result(self, validated_form, assumed=False):
		result = ProofLevel.Result(validated_form, assumed=assumed)
		self.results.append(result)

	def mark_last_result(self, name):
		last_result = self.results[-1]
		result = ProofLevel.Result(last_result.formula, name, last_result.assumed)
		self.results[-1] = result


@contextmanager
def push_new_proof_level():
	previous = top_frame.proof_level
	top_frame.proof_level = ProofLevel(previous)
	try:
		yield top_frame.proof_level
	except:
		raise
	finally:
		top_frame.proof_level = previous


def init_frame_builtins(frame):
	frame.symbol_table.update(jbuiltins.symbol_table)

top_frame = Stackframe(None, "base frame", ProofLevel(None))
init_frame_builtins(top_frame)


def top_level_evaluate(form):
	debug(f"top_level_evaluate( {form} )")
	try:
		evaluate(form)
		if not (isinstance(form, Comment) or isinstance(form, ProofAnnotation)):
			top_frame.proof_level.last_form = form
		return True
	except JimmyError as e:
		import sys
		print(format_error(e), file=sys.stderr)
		return False


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
				return True
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
		raise JimmyError(compound, "Invocation target is invalid.")

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
