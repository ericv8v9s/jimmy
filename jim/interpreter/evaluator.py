import jim.evaluator.evaluator as evaluator
from jim.evaluator.errors import UndefinedVariableError
from .builtins import builtin_symbols


class Context(evaluator.AbstractContext):
	def __init__(self, parent, bindings={}):
		self.parent = parent
		self.symbol_table = dict(bindings)

	def __getitem__(self, name):
		try:
			return self.symbol_table[name]
		except KeyError as e:
			if self.parent is not None:
				return self.parent[name]
			raise UndefinedVariableError(name) from e

	def __setitem__(self, key, val):
		self.symbol_table[key] = val

	def copy(self):
		return Context(self.parent, self.symbol_table)


root_context = Context(None, builtin_symbols)

def evaluate(obj):
	return evaluator.evaluate(obj, root_context)
