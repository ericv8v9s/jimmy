from collections import deque
from contextlib import contextmanager

import jim.builtins
from jim.errors import *


class Stackframe:
	def __init__(self, last_frame, call_form):
		self.last_frame = last_frame
		self.call_form = call_form
		self.symbol_table = dict()

	def lookup(self, symbol):
		try:
			return self.symbol_table[symbol]
		except KeyError:
			if self.last_frame is not None:
				return self.last_frame.lookup(symbol)
			raise UndefinedVariableError(symbol, "Variable is undefined.")


top_frame = Stackframe(None, "base frame")
top_frame.symbol_table = {
	# TODO initialize builtins
	# builtin core stuff
	"nil"   : jim.builtins.nil,
	"true"  : True,
	"false" : False,
	"list"  : jim.builtins.List,
	"assign": jim.builtins.Assignment,
	"func"  : jim.builtins.Lambda,
	"cond"  : jim.builtins.Cond,
	"while" : jim.builtins.While,
	# arithmetic
	"+"     : jim.builtins.Addition,
	"-"     : jim.builtins.Subtraction,
	"*"     : jim.builtins.Multiplication,
	"/"     : jim.builtins.Division,
	"%"     : jim.builtins.(...),
	# tests
	"="     : jim.builtins.(...),
	"<"     : jim.builtins.(...),
	">"     : jim.builtins.(...),
	"<="    : jim.builtins.(...),
	">="    : jim.builtins.(...),
	"and"   : jim.builtins.(...),
	"or"    : jim.builtins.(...),
	"not"   : jim.builtins.(...)
}

def iter_stack():
	f = top_frame
	while f is not None:
		yield f
		f = f.last_frame


@contextmanager
def new_stackframe(call_form):
	global top_frame
	top_frame = Stackframe(top_frame, call_form)
	yield top_frame
	top_frame = top_frame.last_frame


def evaluate(form):
	"""Computes a value for the form parsed by reader."""

	if isinstance(form, tuple):
		return evaluate_atom(form)
	elif isinstance(form, list):
		# empty form is nil literal
		if len(form) == 0:
			return nil

		execution = evaluate(form[0])
		argv = form[1:]

		if isinstance(execution, Macro):
			return evaluate(invoke(form, execution, argv))
		else:
			argv = [evaluate(arg) for arg in argv]
			return invoke(form, execution, argv)
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
	with new_stackframe(form):
		#top_frame.update(parse_argv(execution.parameters, argv))
		pi = 0
		can_accept = len(execution.parameter_spec) > 0
		satisfied = all(map(lambda spec: isinstance(spec, list),
				execution.parameter_spec))

		for arg in argv:
			if not can_accept:
				# TODO

		return execution.run(top_frame)
