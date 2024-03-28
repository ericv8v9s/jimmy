class ProofError(Exception):
	def __init__(self, proof_line, msg):
		super().__init__()
		self.proof_line = proof_line
		self.msg = msg


class UnknownNamedResultError(ProofError):
	def __init__(self, proof_line, name):
		super().__init__(proof_line, f"'{name}' does not name a known result.")


class RuleFormMismatchError(ProofError):
	def __init__(self, proof_line, rule_name, form):
		super().__init__(
				proof_line, f"Rule '{rule_name}' cannot by applied to {form}")


class SyntaxError(ProofError): pass


def format_error(e):
	return (
			 "The following proof line failed to validate\n"
			f"  {e.proof_line}\n"
			f"{e.msg}")
