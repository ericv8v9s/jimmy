import jim.objects as lang
import jim.evaluator.evaluator as evaluator
import jim.evaluator.builtins as builtins


class Execution:
	def __init__(self, parameter_spec):
		# (fn (x y (rest)) body...)
		self.parameter_spec = parameter_spec

	def context(self, locals):
		"""
		The context to evaluate this execution in.
		Different types of executions will requrie different contexts
		(e.g. functions care about closures).
		"""
		return evaluator.top_frame.context

	def evaluate(self, context, **locals):
		# Technically, we don't need locals, as that can exist as another context
		# on top of the provided context.
		# However, every execution defines a parameter_spec and the evaluator
		# already matched up all the arguments before calling evaluate,
		# so as a convenience it is passed on into here.
		# For most builtin executions, this is handy.
		# For jimmy functions, locals is never used, but also not a problem.
		pass


class EvaluateIn: pass
class EvaluateOut: pass


class Function(Execution, EvaluateIn):
	def __init__(self, parameter_spec):
		super().__init__(parameter_spec)

class Macro(Execution, EvaluateOut):
	def __init__(self, parameter_spec):
		super().__init__(parameter_spec)


class UserFunction(Function):
	def __init__(self, parameter_spec, code, parent_context):
		super().__init__(parameter_spec)
		self.code = code
		self.parent_context = parent_context

	def context(self, locals):
		return evaluator.Context(self.parent_context, locals)

	def evaluate(self, context, **locals):
		last = builtins.nil
		for form in self.code:
			last = evaluator.evaluate(form)
		return last


class ArgumentMismatchError(Exception):
	pass

def fill_parameters(parameter_spec, arguments) -> dict[str, lang.Form]:
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
			params[p[0]] = lang.List(arguments[arg_idx:])
			arg_idx += len(params[p[0]])

	if arg_idx != len(arguments):
		raise ArgumentMismatchError
	return params
