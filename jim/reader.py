from string import whitespace, digits, ascii_letters
from functools import wraps
from dataclasses import dataclass
from typing import Any


_SPACES = set(whitespace)
_DIGITS = set(digits)
_LETTERS = set(ascii_letters)
_PUNCTS = set('''!#$%&*+-/:<=>?@\^_~''')
_IDENT_CHARS = _LETTERS | _PUNCTS | _DIGITS


_line_num = 1

class ParseError(Exception):
	def __init__(self, msg):
		super().__init__()
		self.msg = msg
		self.line = _line_num
	def __str__(self):
		return f"Parsing error on line {self.line}: {self.msg}"


_buffer = []
_next_char = 0


@dataclass
class ParseResult:
	success: bool
	result: Any = None
	chars_consumed_adj: int = None


def _component_parser(parse_function):
	@wraps(parse_function)
	def wrapper(get_next_char):
		global _next_char
		bookmark = _next_char

		out = parse_function(get_next_char)
		if out.chars_consumed_adj is not None:
			_next_char += out.chars_consumed_adj
		elif not out.success:
			_next_char = bookmark

		#print(f"DEBUG: {parse_function.__name__}: ", end="")
		#if out.success:
		#	print(f"consumed '{''.join(_buffer[bookmark:_next_char])}'")
		#else:
		#	print("failed")

		return out

	return wrapper


def _make_get_next_char(char_src):
	@wraps(char_src)
	def get_next_char():
		global _next_char
		while _next_char >= len(_buffer):
			_buffer.append(char_src())
		out = _buffer[_next_char]
		_next_char += 1
		return out
	return get_next_char


def parse(char_src):
	get_next_char = _make_get_next_char(char_src)

	skip(get_next_char)
	if _lookahead_eof(get_next_char).success:
		return None

	return parse_form(get_next_char).result

@_component_parser
def _lookahead_eof(get_next_char):
	return ParseResult(get_next_char() == "")


def skip(get_next_char):
	skip_whitespace(get_next_char)
	skip_comment(get_next_char)
	skip_whitespace(get_next_char)

@_component_parser
def skip_whitespace(get_next_char):
	while get_next_char() in _SPACES:
		pass
	return ParseResult(True, chars_consumed_adj=-1)

@_component_parser
def skip_comment(get_next_char):
	if get_next_char() != ';':
		return ParseResult(False)
	while get_next_char() != '\n':
		pass
	return ParseResult(True)


@_component_parser
def parse_form(get_next_char):
	order = [
		parse_compound,
		parse_string,
		parse_integer,
		parse_symbol]

	skip(get_next_char)
	for parse_function in order:
		out = parse_function(get_next_char)
		if out.success:
			# adjustment already applied by the parse_function
			return ParseResult(True, out.result)

	raise ParseError("Invalid form.")


@_component_parser
def parse_compound(get_next_char):
	if get_next_char() != '(':
		return ParseResult(False)
	elements = []
	while not _lookahead_compound_close(get_next_char).success:
		elements.append(parse_form(get_next_char).result)
	return ParseResult(True, elements)


@_component_parser
def _lookahead_compound_close(get_next_char):
	return ParseResult(get_next_char() == ')')


@_component_parser
def parse_integer(get_next_char):
	num_str = []
	c = get_next_char()
	if c == '+' or c == '-':
		num_str.append(c)
		c = get_next_char()

	if c not in _DIGITS:
		return ParseResult(False)

	while c in _DIGITS:
		num_str.append(c)
		c = get_next_char()
	return ParseResult(True, ("LIT", int("".join(num_str))), -1)


@_component_parser
def parse_string(get_next_char):
	if get_next_char() != '"':
		return ParseResult(False)

	s = []
	c = get_next_char()
	while c != '"':
		if c == '//':
			c = get_next_char()
		if c == "":
			raise ParseError("Unterminated string literal.")
		s.append(c)
		c = get_next_char()

	return ParseResult(True, ("LIT", "".join(s)))


@_component_parser
def parse_symbol(get_next_char):
	s = []
	c = get_next_char()
	while c in _IDENT_CHARS:
		s.append(c)
		c = get_next_char()
	if len(s) > 0:
		return ParseResult(True, ("SYM", "".join(s)), -1)
	return ParseResult(False)

