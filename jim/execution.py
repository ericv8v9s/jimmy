import jim.interpreter
import jim.builtins


class Execution:
	def __init__(self, parameter_spec):
		# (func (x y (rest)) body...)
		self.parameter_spec = parameter_spec

	def evaluate(self, stack_frame):
		pass


class EvaluateIn: pass
class EvaluateOut: pass


class Function(Execution, EvaluateIn):
	def __init__(self, parameter_spec):
		super().__init__(parameter_spec)

class Macro(Execution, EvaluateOut):
	def __init__(self, parameter_spec):
		super().__init__(parameter_spec)


class JimmyFunction(Function):
	def __init__(self, parameter_spec, code):
		super().__init__(parameter_spec)
		self.code = code

	def evaluate(self, stack_frame):
		last = jim.builtins.nil
		for form in self.code:
			last = jim.interpreter.evaluate(form)
		return last
