from contextlib import contextmanager

import jim.builtins
import jim.execution as jexec
from jim.errors import *
from jim.syntax import *


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


def init_frame_builtins(frame):
	frame.symbol_table.update({
		# builtin core stuff
		"nil"   : jim.builtins.nil,
		"true"  : True,
		"false" : False,
		"assert": jim.builtins.Assertion(),
		"assign": jim.builtins.Assignment(),
		"func"  : jim.builtins.Lambda(),
		"progn" : jim.builtins.Progn(),
		"cond"  : jim.builtins.Conditional(),
		"while" : jim.builtins.WhileLoop(),

		# arithmetic
		"+": jim.builtins.Addition(),
		"-": jim.builtins.Subtraction(),
		"*": jim.builtins.Multiplication(),
		"/": jim.builtins.Division(),
		"%": jim.builtins.Modulo(),

		# tests
		"="  : jim.builtins.Equality(),
		"<"  : jim.builtins.LessThan(),
		">"  : jim.builtins.GreaterThan(),
		"<=" : jim.builtins.LessEqual(),
		">=" : jim.builtins.GreaterEqual(),
		"and": jim.builtins.Conjunction(),
		"or" : jim.builtins.Disjunction(),
		"not": jim.builtins.Negation(),

		"print"   : jim.builtins.Print(),
		"list"    : jim.builtins.List(),
		"list-get": jim.builtins.ListGet(),
		"list-set": jim.builtins.ListSet(),
		"len"     : jim.builtins.Length()
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
		return evaluate(form)
	except JimmyError as e:
		import sys
		print(format_error(e), file=sys.stderr)


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
				return jim.builtins.nil
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



def main(argv):
	from jim import reader
	import sys

	match argv:
		case []:  # interactive mode
			while True:
				print("IN: ", end="", flush=True)

				try:
					parsed = reader.parse(lambda: sys.stdin.read(1))
				except reader.ParseError as e:
					print(str(e), file=sys.stderr)
					break

				if parsed is None:
					break

				result = top_level_evaluate(parsed)
				if result is not None:
					print("OUT:", result, flush=True)

		case [filename]:
			if filename == "-":
				f = sys.stdin
			else:
				f = open(filename)
			with f:
				while True:
					try:
						form = reader.parse(lambda: f.read(1))
					except reader.ParseError as e:
						print(str(e), file=sys.stderr)
						break
					if form is None:
						break
					#print("REPROD:", str(form).rstrip())
					top_level_evaluate(form)

		case _:
			from jim import main
			main.print_usage()
