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


class ArgumentMismatchError(Exception):
	pass

def fill_parameters(parameter_spec, arguments):
	params = dict()  # collects arguments to match up with parameters
	arg_idx = 0

	for p in parameter_spec:
		if isinstance(p, str):  # positional
			if arg_idx < len(arguments):
				params[p] = arguments[arg_idx]
				arg_idx += 1
			else:
				raise ArgumentMismatchError
		elif isinstance(p, list):  # rest
			params[p[0]] = arguments[arg_idx:]
			arg_idx += len(params[p[0]])
	return params
