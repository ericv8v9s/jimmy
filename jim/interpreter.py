from collections import deque
from contextlib import contextmanager

import jim.builtins
import jim.utils as utils
import jim.execution as jexec
from jim.errors import *


class Stackframe:
	def __init__(self, last_frame, call_form):
		self.last_frame = last_frame
		self.call_form = call_form
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


top_frame = Stackframe(None, "base frame")
top_frame.symbol_table = {
	# TODO initialize builtins
	# builtin core stuff
	"nil"   : jim.builtins.nil,
	"true"  : True,
	"false" : False,
	#"list"  : jim.builtins.List(),
	"assign": jim.builtins.Assignment(),
	"func"  : jim.builtins.Lambda(),
	"progn" : jim.builtins.Progn(),
	"cond"  : jim.builtins.Conditional(),
	#"while" : jim.builtins.While(),
	# arithmetic
	"+"     : jim.builtins.Addition(),
	"-"     : jim.builtins.Subtraction(),
	"*"     : jim.builtins.Multiplication(),
	"/"     : jim.builtins.Division(),
	"%"     : jim.builtins.Modulo(),
	# tests
	"="     : jim.builtins.Equality(),
	"<"     : jim.builtins.LessThan(),
	">"     : jim.builtins.GreaterThan(),
	"<="    : jim.builtins.LessEqual(),
	">="    : jim.builtins.GreaterEqual(),
	"and"   : jim.builtins.Conjunction(),
	"or"    : jim.builtins.Disjunction(),
	"not"   : jim.builtins.Negation(),

	"print" : jim.builtins.Print()
}

def iter_stack():
	f = top_frame
	while f is not None:
		yield f
		f = f.last_frame


@contextmanager
def push_new_frame(call_form):
	global top_frame
	top_frame = Stackframe(top_frame, call_form)
	yield top_frame
	top_frame = top_frame.last_frame


@contextmanager
def switch_stack(new_top_frame):
	global top_frame
	saved = top_frame
	top_frame = new_top_frame
	yield new_top_frame
	top_frame = saved


def top_level_evaluate(form):
	try:
		return evaluate(form)
	except JimmyError as e:
		import sys
		print(format_error(e), file=sys.stderr)

def evaluate(form):
	"""Computes a value for the form parsed by reader."""

	#print(f"DEBUG: evaluate( {utils.form_to_str(form)} )")

	if isinstance(form, tuple):
		return evaluate_atom(form)
	elif isinstance(form, list):
		# empty form is nil literal
		if len(form) == 0:
			return nil

		execution = evaluate(form[0])
		argv = form[1:]

		if isinstance(execution, jexec.Macro):
			return evaluate(invoke(form, execution, argv))
		elif isinstance(execution, jexec.Function):
			argv = [evaluate(arg) for arg in argv]
			return invoke(form, execution, argv)
		else:
			raise JimmyError(form, "Invocation target is invalid.")
	else:  # otherwise, consider it to be a raw object already evaluated
		return form


def evaluate_atom(atom):
	t, v = atom
	if t == "LIT":
		return v
	if t == "SYM":
		return top_frame.lookup(v)
	assert False


def invoke(form, execution, argv):
	#print(f"DEBUG: invoke({form}, {execution}, {argv})")

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

	with push_new_frame(form) as f:
		f.symbol_table.update(params)
		return execution.evaluate(f)
