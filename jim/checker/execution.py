class Execution:
	def __init__(self, parameter_spec):
		# (func (x y (rest)) body...)
		self.parameter_spec = parameter_spec

	def evaluate(self, proof_level, args_dict):
		pass


class EvaluateIn: pass
class EvaluateOut: pass


class Function(Execution, EvaluateIn):
	def __init__(self, parameter_spec):
		super().__init__(parameter_spec)

class Macro(Execution, EvaluateOut):
	def __init__(self, parameter_spec):
		super().__init__(parameter_spec)
