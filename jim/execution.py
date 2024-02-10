import jim.interpreter
from jim.builtins import nil


class Execution:
	def __init__(self, *parameter_spec):
		# (func (x y (rest)) body...)
		self.parameter_spec = parameter_spec

	def evaluate(self, stack_frame):
		pass


class Function(Execution):
	pass

class Macro(Execution):
	pass


class JimmyProcedure(Execution):
	def __init__(self, *parameter_spec, code):
		super().__init__(parameter_spec)
		self.code = code

	def evaluate(self, stack_frame):
		last = nil
		for form in self.code:
			jim.interpreter.evaluate(form)
