import jim.evaluator.evaluator as evaluator

def evaluate(obj, context):
	return evaluator.top_level_evaluate(obj, context)
