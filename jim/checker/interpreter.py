from contextlib import contextmanager

import jim.executor.builtins as jimlang
import jim.executor.execution as jexec
from .errors import *
from jim.syntax import *


# Like stack frames.
# Each proof has its proof level,
# and each sub-proof gets a new proof level on top of the previous.
class ProofLevel:
	def __init__(self, previous_level):
		self.previous = previous_level
		self.results = []
		self.named_results = dict()
		self.last_result = None
		self.last_form = None
		self.current_proof_line = None

	def lookup(self, name):
		"""Looks up a named result."""
		try:
			return self.named_results[name]
		except KeyError:
			if self.previous is not None:
				return self.previous.lookup(name)
			raise

	def __getitem__(self, key):
		return self.known_formulas[key]


def init_frame_builtins(frame):
	frame.symbol_table.update({
		# builtin core stuff
		"nil"   : jimlang.nil,
		"true"  : True,
		"false" : False,
		"assert": jimlang.Assertion(),
		"assign": jimlang.Assignment(),
		"func"  : jimlang.Lambda(),
		"progn" : jimlang.Progn(),
		"cond"  : jimlang.Conditional(),
		"while" : jimlang.WhileLoop(),

		# arithmetic
		"+": jimlang.Addition(),
		"-": jimlang.Subtraction(),
		"*": jimlang.Multiplication(),
		"/": jimlang.Division(),
		"%": jimlang.Modulo(),

		# tests
		"="  : jimlang.Equality(),
		"<"  : jimlang.LessThan(),
		">"  : jimlang.GreaterThan(),
		"<=" : jimlang.LessEqual(),
		">=" : jimlang.GreaterEqual(),
		"and": jimlang.Conjunction(),
		"or" : jimlang.Disjunction(),
		"not": jimlang.Negation(),

		"print"   : jimlang.Print(),
		"list"    : jimlang.List(),
		"list-get": jimlang.ListGet(),
		"list-set": jimlang.ListSet(),
		"len"     : jimlang.Length()
	})


top_frame = Stackframe(None, "base frame")
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


def top_level_evaluate(form):
	try:
		evaluate(form)
		return True
	except ProofError as e:
		import sys
		print(format_error(e), file=sys.stderr)
		return False


def evaluate(obj):
	"""Computes a value for the form parsed by reader."""

	#print(f"DEBUG: evaluate( {obj} )")

	match obj:
		case Integer(value=v):
			return v
		case Symbol(value=name):
			return top_frame.lookup(name)
		case String(value=s):
			return s

		case CompoundForm(children=forms):
			if len(forms) == 0:
				return jimlang.nil
			return invoke(obj)

		case CodeObject():
			# comments and proof annotations are noops
			return None

		case _:
			# consider it to be a raw object already evaluated
			return obj


def invoke(compound):
	execution = evaluate(compound[0])
	argv = compound[1:]

	if not isinstance(execution, jexec.Execution):
		raise JimmyError(form, "Invocation target is invalid.")

	if isinstance(execution, jexec.EvaluateIn):
		argv = [evaluate(arg) for arg in argv]

	#print(f"DEBUG: invoke: ({execution} {argv})")

	params = dict()  # collects arguments to match up with parameters
	argv_idx = 0

	for p in execution.parameter_spec:
		if isinstance(p, str):  # positional
			if argv_idx < len(argv):
				params[p] = argv[argv_idx]
				argv_idx += 1
			else:
				raise ArgumentMismatchError(form)
		elif isinstance(p, list):  # rest
			params[p[0]] = argv[argv_idx:]
			argv_idx += len(params[p[0]])

	with push_new_frame(compound) as f:
		f.symbol_table.update(params)
		result = execution.evaluate(f)

	if isinstance(execution, jexec.EvaluateOut):
		return evaluate(result)
	else:
		return result
