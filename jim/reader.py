"""
The reader: string in, forms out.
"""

from string import whitespace, digits, ascii_letters

_IDENT_FIRST_CHARS = ascii_letters + '''!$%&*+-/:;<=>?@\^_~'''
_IDENT_CHARS = _IDENT_FIRST_CHARS + digits


# incomplete input
_buf = ""
_balance = 0  # count '(' - count ')'


def feed(chunk: str) -> list:
	global _buf, _balance

	if len(chunk) == 0:
		return []

	m = _match_pair(chunk, balance=_balance)
	if m >= 0:
		_balance = 0
		text = _preprocess(_buf + chunk[:m+1])
		_buf = ""
		print(f"DEBUG: text='{text}'")
		if len(text) == 0:
			return feed(chunk[m+1:])
		return [parse(text)] + feed(chunk[m+1:])

	else:
		_balance = -(m + 1)
		_buf += chunk
		return []


def _preprocess(text: str) -> str:
	lines = text.split("\n")
	for i, line in enumerate(lines):
		lines[i] = line.split("#", maxsplit=1)[0]
	return "\n".join(lines).strip()


def _match_pair(s, balance=0) -> int:
	"""
	Returns the first index such that L + balance = R,
	where L is the number of open parentheses before or at index
	and R is the number of close parentheses before or at index.
	If such an index does not exist, returns -(number of extra left items + 1).
	Parentheses quoted in strings are not counted.
	"""
	quoted = False
	for i, c in enumerate(s):
		if quoted:
			if c == '"':
				quoted = False
			continue

		if c == '"':
			quoted = True
		elif c == '(':
			balance += 1
		elif c == ')':
			balance -= 1

		if balance == 0:
			return i

	return -(balance + 1)


def parse(form_str: str) -> list:
	"""Parses a complete form."""
	print(f"DEBUG: '{form_str}'")
	parts = []
	idx = 0

	def START():
		nonlocal idx
		assert form_str[idx] == '('
		idx += 1
		return CONTINUE

	def CONTINUE():
		nonlocal idx
		c = form_str[idx]
#		if c == '#':
#			return COMMENT
		if c == '(':
			subform_end = idx + _match_pair(form_str[idx:])
			assert subform_end > idx
			parts.append(parse(form_str[idx:subform_end+1]))
			idx = subform_end + 1
			return CONTINUE
		elif c == '"':
			return LITERAL_STR
		elif c in digits:
			return LITERAL_INT
		elif c in whitespace:
			idx += 1
			return CONTINUE
		elif c in _IDENT_FIRST_CHARS:
			return IDENTIFIER
		elif c == ')':
			assert idx == len(form_str)-1
			return STOP
		else:
			raise ValueError("illegal character: " + c)

#	def COMMENT():
#		nonlocal idx
#		while idx < len(form_str) and form_str[idx] != '\n':
#			idx += 1
#		return CONTINUE

	def LITERAL_STR():
		nonlocal idx
		idx += 1
		s = ""
		while idx < len(form_str):
			c = form_str[idx]
			if c == '\\':
				s += form_str[idx+1]
				idx += 2
				continue
			if c == '"':
				parts.append(("LIT", s))
				idx += 1
				return CONTINUE
			else:
				s += c
				idx += 1
		raise ValueError("string not terminated")

	def LITERAL_INT():
		nonlocal idx
		c = form_str[idx]
		s = ""
		while idx < len(form_str):
			c = form_str[idx]
			if c in digits:
				s += c
				idx += 1
			elif c in whitespace or c in "()":
				parts.append(("LIT", int(s)))
				return CONTINUE
			else:
				raise ValueError("bad integer literal")
		raise ValueError("form incomplete")

	def IDENTIFIER():
		nonlocal idx
		s = ""
		while idx < len(form_str):
			c = form_str[idx]
			if c in _IDENT_CHARS:
				s += c
				idx += 1
			else:
				parts.append(("SYM", s))
				return CONTINUE
		raise ValueError("form incomplete")

	def STOP(): pass

	state = START
	while state != STOP:
		state = state()

	return parts
