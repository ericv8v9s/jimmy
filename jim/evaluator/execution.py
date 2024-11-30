import jim.objects as lang
import jim.evaluator.errors as errors


class Execution:
	def __init__(self, parameter_spec):
		# (fn (x y (rest)) body...)
		self.parameter_spec = parameter_spec

	def evaluate(self, calling_context, **locals):
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


class ArgumentMismatchError(Exception):
	"""
	This exists because we want to include more information
	when we raise the real error, which we don't have in fill_parameters.
	"""
	pass

def fill_parameters(parameter_spec, arguments) -> dict[str, lang.Form]:
	params = dict()  # collects arguments to match up with parameters
	arg_idx = 0

	def fill_one_param(param, arg=None):
		nonlocal params, arg_idx
		params[param] = arguments[arg_idx] if arg is None else arg
		arg_idx += 1

	for p in parameter_spec:
		if isinstance(p, str):  # positional
			if arg_idx < len(arguments):
				params[p] = arguments[arg_idx]
				arg_idx += 1
			else:
				raise ArgumentMismatchError

		elif isinstance(p, list):  # optional or rest
			match len(p):
				case 1:  # rest
					params[p[0]] = lang.List(arguments[arg_idx:])
					arg_idx += len(params[p[0]])
				case 2:  # optional
					if arg_idx < len(arguments):
						params[p[0]] = arguments[arg_idx]
						arg_idx += 1
					else:
						params[p[0]] = p[1]
				case _:
					# This shouldn't really happen.
					# Invalid specs would be caught when creating the function,
					# not when it's being called.
					raise errors.JimmyError("The parameter specification is invalid.", p)

	if arg_idx != len(arguments):
		raise ArgumentMismatchError
	return params
