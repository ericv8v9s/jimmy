from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial

import jim.executor.builtins as jimlang
import jim.checker.execution as jexec
from .errors import *
from jim.syntax import *


# Like stack frames.
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
		self.current_line = None

	def lookup(self, name):
		"""Looks up a named result."""
		for result in reversed(results):
			if result.name == name:
				return result.formula
		if self.previous is not None:
			return self.previous.lookup(name)
		raise UnknownNamedResultError(name)


top_frame = ProofLevel(None)


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


def top_level_evaluate(form):
	try:
		evaluate(form, ignore_compound=True)
		return True
	except ProofError as e:
		import sys
		print(format_error(e), file=sys.stderr)
		return False


def evaluate(obj, ignore_compound):
	#print(f"DEBUG: evaluate( {obj} )")

	match obj:
		case ProofAnnotation(children=forms):
			if len(forms) == 0:
				return None
			return invoke(obj)

		case CompoundForm(children=forms) if not ignore_compound:
			if len(forms) == 0:
				return jimlang.nil
			return invoke(obj)

		case Integer(value=v):
			return v
		case Symbol(value=name):
			return top_frame.lookup(name)
		case String(value=s):
			return s

		case CodeObject():
			return None

		case _:
			# consider it to be a raw object already evaluated
			return obj


def invoke(compound):
	eval_also_compound = partial(evaluate, ignore_compound=False)

	execution = eval_also_compound(compound[0])
	argv = compound[1:]

	if not isinstance(execution, jexec.Execution):
		raise ProofError("Invocation target is invalid.")

	if isinstance(execution, jexec.EvaluateIn):
		argv = [eval_also_compound(arg) for arg in argv]

	#print(f"DEBUG: invoke: ({execution} {argv})")

	params = dict()  # collects arguments to match up with parameters
	argv_idx = 0

	for p in execution.parameter_spec:
		if isinstance(p, str):  # positional
			if argv_idx < len(argv):
				params[p] = argv[argv_idx]
				argv_idx += 1
			else:
				raise ArgumentMismatchError(compound[0], argv)
		elif isinstance(p, list):  # rest
			params[p[0]] = argv[argv_idx:]
			argv_idx += len(params[p[0]])

	result = execution.evaluate(top_frame, params)

	if isinstance(execution, jexec.EvaluateOut):
		return eval_also_compound(result)
	else:
		return result
