"""
The reader: string in, forms out.

Character source discipline:
The parse function takes input from a character source (get_next_char).
This means characters are consumed one at a time,
and that once consumed they cannot be put back.
A buffer is used to remedy this.

Each of the specialized parse functions (parse_form, parse_str, etc.)
expect the next call to get_next_char to produce the very first character
within the relevant object.
For parse_form, for example, the first call of get_next_char must return a '('.
Consequently, upon completion of a parse, the function is responsible for
putting back any character(s) consumed to determine termination,
but are not part of the object being parsed.
"""

from string import whitespace, digits, ascii_letters
from collections import deque

_SPACES = set(whitespace)
_DIGITS = set(digits)
_LETTERS = set(ascii_letters)
_PUNCTS = set('''!#$%&*+-/:<=>?@\^_~''')

_IDENT_FIRST_CHARS = _LETTERS | _PUNCTS
_IDENT_CHARS = _IDENT_FIRST_CHARS | _DIGITS


_buffer = deque()

def _wrap_char_source(get_next_char):
	def wrapper():
		if len(_buffer) > 0:
			return _buffer.popleft()
		return get_next_char()
	return wrapper

def _put_back(c):
	_buffer.appendleft(c)


def parse(get_next_char):
	get_next_char = _wrap_char_source(get_next_char)

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

	_put_back(c)

	return pf(get_next_char)


def parse_form(get_next_char) -> list:
	c = get_next_char()
	assert c == '('

	elements = []
	while True:
		c = get_next_char()
		if c in _SPACES:
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
			return elements
		elif c == "":
			raise EOFError
		else:
			raise ValueError(f"illegal character: '{c}'")

		_put_back(c)
		elements.append(pf(get_next_char))

	assert False


def parse_str(get_next_char) -> tuple[str, str]:
	c = get_next_char()
	assert c == '"'
	s = ""
	while True:
		c = get_next_char()
		if c == '\\':
			s += get_next_char()
			c = get_next_char()
		elif c == '"':
			return ("LIT", s)
		elif c == "":
			raise EOFError
		else:
			s += c
	assert False


def parse_int(get_next_char) -> tuple[str, int]:
	s = get_next_char()
	while True:
		c = get_next_char()
		if c in _SPACES or c == '(' or c == ')' or c == "":
			_put_back(c)
			return ("LIT", int(s))
		elif c in _DIGITS:
			s += c
		else:
			raise ValueError("bad integer literal")
	assert False


def parse_symbol(get_next_char) -> tuple[str, str]:
	s = get_next_char()
	while True:
		c = get_next_char()
		if c in _IDENT_CHARS:
			s += c
		else:
			_put_back(c)
			return ("SYM", s)
	assert False
