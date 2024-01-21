"""
The reader: string in, forms out.
"""

from string import whitespace, digits, ascii_letters
_SPACES = set(whitespace)
_DIGITS = set(digits)
_LETTERS = set(ascii_letters)
_PUNCTS = set('''!#$%&*+-/:<=>?@\^_~''')

_IDENT_FIRST_CHARS = _LETTERS | _PUNCTS
_IDENT_CHARS = _IDENT_FIRST_CHARS | _DIGITS


def parse(get_next_char):
	c = get_next_char()
	while True:
		if c in _SPACES:
			c = get_next_char()
		elif c == ';':
			while c != '\n':
				c = get_next_char()
		else:
			break

	if c == '(':
		pf = parse_form
	elif c == '"':
		pf = parse_str
	elif c in _DIGITS:
		pf = parse_int
	elif c in _IDENT_FIRST_CHARS:
		pf = parse_symbol
	elif c == "":
		return None
	else:
		raise ValueError(f"illegal character: '{c}'")

	return pf(c, get_next_char)[1]


def parse_form(current_char, get_next_char) -> tuple[str, list]:
	assert current_char == '('
	c = get_next_char()
	elements = []
	while True:
		if c in _SPACES:
			c = get_next_char()
			continue
		if c == '(':
			pf = parse_form
		elif c == '"':
			pf = parse_str
		elif c in _DIGITS:
			pf = parse_int
		elif c in _IDENT_FIRST_CHARS:
			pf = parse_symbol
		elif c == ')':
			return (get_next_char(), elements)
		elif c == "":
			raise EOFError
		else:
			raise ValueError(f"illegal character: '{c}'")
		c, ele = pf(c, get_next_char)
		elements.append(ele)
	assert False


def parse_str(current_char, get_next_char) -> tuple[str, tuple[str, str]]:
	assert current_char == '"'
	s = ""
	while True:
		c = get_next_char()
		if c == '\\':
			s += get_next_char()
			c = get_next_char()
		elif c == '"':
			return (get_next_char(), ("LIT", s))
		elif c == "":
			raise EOFError
		else:
			s += c
	assert False


def parse_int(current_char, get_next_char) -> tuple[str, tuple[str, int]]:
	s = current_char
	while True:
		c = get_next_char()
		if c in _SPACES or c == '(' or c == ')' or c == "":
			return (c, ("LIT", int(s)))
		elif c in _DIGITS:
			s += c
		else:
			raise ValueError("bad integer literal")
	assert False


def parse_symbol(current_char, get_next_char) -> tuple[str, tuple[str, str]]:
	s = current_char
	while True:
		c = get_next_char()
		if c in _IDENT_CHARS:
			s += c
		else:
			return (c, ("SYM", s))
	assert False
