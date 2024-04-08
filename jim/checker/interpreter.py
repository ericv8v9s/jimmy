from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial

import jim.checker.builtins as jbuiltins
import jim.checker.execution as jexec
from .errors import *
from jim.syntax import *


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
			self.proof_level = last_form.proof_level
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

	def lookup_result(self, name):
		return self.proof_level.lookup(name)


def init_frame_builtins(frame):
	frame.symbol_table.update(jbuiltins.symbol_table)

top_frame = Stackframe(None, "base frame", ProofLevel(None))
init_frame_builtins(top_frame)


def iter_stack():
	f = top_frame
	while f is not None:
		yield f
		f = f.last_frame


@contextmanager
def push_new_frame(call_form):
	#print(f"DEBUG: PUSH: {call_form}")
	global top_frame
	top_frame = Stackframe(top_frame, call_form)
	try:
		yield top_frame
	except:
		raise
	finally:
		top_frame = top_frame.last_frame
		#print(f"DEBUG: POP: {call_form}")


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
	@dataclass
	class Result:
		formula: Form
		name: str = None
		assumed: bool = False  # prbly necessary if we add quantifiers

	def __init__(self, previous_level):
		self.previous = previous_level
		self.results: list[Result] = []
		self.last_form = None

	def lookup(self, name):
		"""Looks up a named result."""
		for result in reversed(self.results):
			if result.name == name:
				return result.formula
		if self.previous is not None:
			return self.previous.lookup(name)
		raise UnknownNamedResultError(name)

	def add_result(self, validated_form, assumed=False):
		result = ProofLevel.Result(validated_form, assumed=assumed)
		self.results.append(result)

	def mark_last_result(self, name):
		last_result = self.results[-1]
		result = Result(last_result.formula, name, last_result.assumed)
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


def top_level_evaluate(form):
	try:
		evaluate(form)
	except JimmyError as e:
		import sys
		print(format_error(e), file=sys.stderr)


def evaluate(obj, ignore_compound=True):
	#print(f"DEBUG: evaluate( {obj} )")

	match obj:
		case Integer(value=v):
			return v
		case Symbol(value=name):
			return top_frame.lookup(name)
		case String(value=s):
			return s

		case ProofAnnotation(children=forms):
			if len(forms) == 0:
				return True
			return invoke(obj)

		# special case for progn, always evaluated
		case CompoundForm(children=[Symbol(value="progn"), *body]):
			for form in body:
				evaluate(form)

		case CompoundForm(children=forms) if not ignore_compound:
			if len(forms) == 0:
				return jimlang.nil
			return invoke(obj)

		case CodeObject():
			return None

		case _:
			# consider it to be a raw object already evaluated
			return obj


def invoke(compound):
	# We are calling something.
	# This only possible if we are invoking a proof annotation as a call form
	# or a compound form within a proof annotation.
	# In either case, further compound forms should also be evaluated.
	eval_also_compound = partial(evaluate, ignore_compound=False)

	execution = eval_also_compound(compound[0])
	argv = compound[1:]

	if not isinstance(execution, jexec.Execution):
		raise ProofError("Invocation target is invalid.")

	if isinstance(execution, jexec.EvaluateIn):
		argv = [eval_also_compound(arg) for arg in argv]

	#print(f"DEBUG: invoke: ({execution} {argv})")

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
