import jim.objects
import jim.executor.interpreter as interpreter
import jim.executor.builtins as jimlang


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
		return interpreter.top_frame.context

	def evaluate(self, context, **locals):
		# Technically, we don't need locals, as that can exist as another context
		# on top of the provided context.
		# However, every execution defines a parameter_spec and the interpreter
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


class JimmyFunction(Function):
	def __init__(self, parameter_spec, code, closure):
		super().__init__(parameter_spec)
		self.code = code
		self.closure = closure

	def context(self, locals):
		return interpreter.Context(self.closure, **locals)

	def evaluate(self, context, **locals):
		last = jimlang.nil
		for form in self.code:
			last = interpreter.evaluate(form)
		return last


class ArgumentMismatchError(Exception):
	pass

def fill_parameters(parameter_spec, arguments) -> dict[str, jim.objects.Form]:
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
			params[p[0]] = jim.objects.Array(arguments[arg_idx:])
			arg_idx += len(params[p[0]])
	return params
