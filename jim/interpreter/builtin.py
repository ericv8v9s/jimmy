import jim.evaluator.common_builtin as common
import jim.evaluator.evaluator as evaluator
from jim.evaluator.execution import EvaluateIn
import jim.evaluator.errors as errors
from jim.objects import *


@common.builtin_symbol("fn")
class UserFunction(common.UserExecution):
	class Instance(EvaluateIn, common.UserExecution.Instance):
		def __init__(self, parameter_spec, code, closure):
			super().__init__(parameter_spec, code, closure)


@common.builtin_symbol("loop")
class Loop(common.UserExecution):
	class Instance(UserFunction.Instance):
		def __init__(self, names, body, closure):
			super().__init__(names, body, closure)
			self.alive = True

		def evaluate(self, last_iteration_context, **locals):
			if not self.alive:
				raise errors.JimmyError("Cannot invoke loop iteration outside of loop.")

			body_context = self.closure.new_child(locals)
			body_context["*recur*"] = self
			f = evaluator.push(self.body, body_context)
			yield
			for name in self.parameter_spec:
				last_iteration_context[name] = body_context[name]
			return f.result

	def evaluate(self, context, param_spec, body):
		# Loop instance only accepts positional params corresponding to variables
		# to send back to the calling context.
		def is_symbol(n): return isinstance(n, Symbol)
		if not all(map(is_symbol, param_spec)):
			raise errors.JimmyError("Loop variable is not an identifier.")
		names = list(map(lambda n: n.value, param_spec))

		loop = Loop.Instance(names, common.wrap_progn(body), context)
		f = evaluator.push(List([loop, *param_spec]), context)
		yield
		loop.alive = False
		return f.result
