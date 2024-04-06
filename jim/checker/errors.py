import jim.checker.interpreter as checker


class ProofError(Exception):
	def __init__(self, msg):
		super().__init__()
		self.msg = msg
		self.proof_line = checker.top_frame.current_line


class UnknownNamedResultError(ProofError):
	def __init__(self, name):
		super().__init__(f"'{name}' does not name a known result.")


class RuleFormMismatchError(ProofError):
	def __init__(self, rule_name, form):
		super().__init__(
				f"Rule '{rule_name}' cannot by applied to {form}.")


class ArgumentMismatchError(ProofError):
	def __init__(self, execution, argv):
		super().__init__(
				f"{execution} does not accept arguments: "
				f"{', '.join(map(str, argv))}.")


class SyntaxError(ProofError): pass


def format_error(e):
	return (
			 "The following proof line failed to validate\n"
			f"  {e.proof_line}\n"
			f"{e.msg}")
