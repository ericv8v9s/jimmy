import jim.evaluator.evaluator as evaluator
from .builtins import builtin_symbols


context = evaluator.init_context(builtin_symbols)

def evaluate(obj):
	return evaluator.evaluate(obj, context)
