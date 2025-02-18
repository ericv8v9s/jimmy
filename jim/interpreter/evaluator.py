import jim.evaluator.evaluator as evaluator
from jim.objects import *
from jim.evaluator.errors import *


def evaluate(obj, context):
	#return evaluator.evaluate(obj, context)

	#debug(f"evaluate: {obj}")

	match obj:
		case Symbol(value=name):
			return context[name]

		# Other atoms are self-evaluating objects.
		case Atom():
			return obj

		case List():
			if len(obj) == 0:
				return nil
			try:
				return evaluator.invoke(obj, evaluate, context)
			except JimmyError:
				raise
			except Exception as e:
				# Take the first one that isn't empty.
				raise JimmyError(str(e) or repr(e) or str(type(e)), obj)

		case None:
			# Special case: None means a no-op.
			return None

		case _:
			for i, frame in enumerate(reversed(list(evaluator.iter_stack()))):
				debug(f"{i}: {frame.call_form}")
			debug(f"raw object: {obj}")
			assert False  # We should never see raw python object.
