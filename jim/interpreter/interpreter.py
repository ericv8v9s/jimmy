class SymbolTable:
	def __init__(self, prev):
		super().__init__()
		self.prev = prev
		self.table = dict()

	def __getitem__(self, key):
		return self.table[key]

	def __setitem__(self, key, value):
		return self.table[key] = value


active_table = SymbolTable(None)
# TODO initialize table with built-ins

def push_table():
	active_table = SymbolTable(active_table)

def pop_table():
	active_table = active_table.prev
	assert active_table is not None

def invoke(execution, argv):
	assert len(execution.parameters) == len(argv)
	push_table()
	for param, arg in zip(execution.parameters, argv):
		active_table[param] = arg

	result = execution.run(active_table)

	pop_table()
	return result


def evaluate(form):
	if isinstance(form, tuple):
		return evaluate_atom(form)
	assert isinstance(form, list)

	if len(form) == 0:
		return nil

	execution = evaluate(form[0])
	argv = form[1:]

	if isinstance(execution, Macro):
		# (defun xxx ...) -> manipulate active_table -> ["SYM", "xxx"]
		return evaluate(invoke(execution, argv))
	else:
		argv = [evaluate(arg) for arg in argv]
		return invoke(execution, argv)


def evaluate_atom(atom):
	t, v = atom
	if t == "LIT":
		return v
	if t == "SYM":
		return active_table[v]
	assert False


class Nil:
	def __str__(self):
		return "nil"
nil = Nil()


class Execution:
	def __init__(self, parameters):
		super().__init__()
		self.parameters = parameters

	def run(self, symtab):
		pass


# defun (and defmacro maybe)
class UserDefined(Execution):
	def __init__(self, parameters, text):
		super().__init__(parameters)
		self.text = text

	def run(self, symtab):
		last = None
		for form in text:
			last = evaluate(form)
		return last


class Function(Execution):
	pass

class Macro(Execution):
	pass


class Addition(Function):
	def __init__(self):
		super().__init__(["a", "b"])
	def run(self, symtab):
		return int(symtab["a"]) + int(symtab["b"])

class Subtraction(Function):
	def __init__(self):
		super().__init__(["a", "b"])
	def run(self, symtab):
		return int(symtab["a"]) - int(symtab["b"])

class Multiplication(Function):
	def __init__(self):
		super().__init__(["a", "b"])
	def run(self, symtab):
		return int(symtab["a"]) * int(symtab["b"])

class Division(Function):
	def __init__(self):
		super().__init__(["a", "b"])
	def run(self, symtab):
		return int(symtab["a"]) // int(symtab["b"])


class Print(Function):
	def __init__(self):
		super().__init__(["msg"])
	def run(self, symtab):
		print(symtab["msg"], end="")
		return nil
