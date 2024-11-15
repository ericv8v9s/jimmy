from contextlib import contextmanager
from string import whitespace, digits, ascii_letters
from functools import wraps, cache
from dataclasses import dataclass
from typing import Any

from jim.objects import *


_SPACES = set(whitespace)
_DIGITS = set(digits)
_LETTERS = set(ascii_letters)
_PUNCTS = set(r'!#$%&*+-/:<=>?@\^_~')
_SEPARATORS = set("()[]") | _SPACES | {""}
_IDENT_CHARS = _LETTERS | _PUNCTS | _DIGITS


# The parser is unfortunately stateful...
_line_num = 1
_buffer = []
_next_char = 0

@contextmanager
def fresh_reader_state():
	# This exists for the load function.
	global _line_num, _buffer, _next_char

	_line_num_save = _line_num
	_buffer_save = _buffer
	_next_char_save = _next_char

	_line_num = 1
	_buffer = []
	_next_char = 0

	try:
		yield
	finally:
		_line_num = _line_num_save
		_buffer = _buffer_save
		_next_char = _next_char_save


class ParseError(Exception):
	def __init__(self, msg):
		super().__init__()
		self.msg = msg
		self.line = _line_num
	def __str__(self):
		return f"Parse error on line {self.line}: {self.msg}"


@dataclass
class ParseResult:
	success: bool
	result: Any = None
	chars_consumed_adj: int = None


def _component_parser(parse_function):
	@wraps(parse_function)
	def component_parser_wrapper(char_source):
		global _next_char
		bookmark = _next_char

		# parse logic:
		out = parse_function(char_source)
		#   if the parse function gave a manual adjustment, use that
		if out.chars_consumed_adj is not None:
			_next_char += out.chars_consumed_adj
		#   otherwise, if parsing failed, drop back to bookmark
		elif not out.success:
			_next_char = bookmark

		#print(f"DEBUG: {parse_function.__name__}: ", end="")
		#if out.success:
		#	print(f"consumed '{''.join(_buffer[bookmark:_next_char])}'")
		#else:
		#	print("failed")

		return out
	return component_parser_wrapper


def wrap_char_source(get_next_char):
	"""
	Wraps the character source function into a generator.

	The character source function should not raise errors for EOF,
	and should instead return the empty string.
	"""

	def char_gen():
		global _next_char, _line_num
		while True:
			while _next_char >= len(_buffer):
				c = get_next_char()
				if c == '\n':
					_line_num += 1
				_buffer.append(c)

			out = _buffer[_next_char]
			_next_char += 1
			yield out
	return char_gen()


@cache
def _lookahead1(c):
	@_component_parser
	def lookahead(chars):
		return ParseResult(next(chars) == c)
	return lookahead


def parse(chars):
	skip_whitespace(chars)
	if _lookahead1("")(chars).success:  # empty string indicates EOF
		return None
	return parse_form(chars).result


def load_forms(get_next_char):
	chars = wrap_char_source(get_next_char)
	while True:
		form = parse(chars)
		if form is None:
			break
		if isinstance(form, Comment):
			continue
		yield form


@_component_parser
def skip_whitespace(chars):
	while next(chars) in _SPACES:
		pass
	return ParseResult(True, chars_consumed_adj=-1)


@_component_parser
def parse_form(chars):
	order = [
		parse_comment,
		parse_list,
		parse_string,
		parse_integer,
		parse_symbol]

	skip_whitespace(chars)
	for parse_function in order:
		out = parse_function(chars)
		if out.success:
			# adjustment already applied by wrapper
			return ParseResult(True, out.result)

	raise ParseError("Invalid form.")


@_component_parser
def parse_list(chars):
	if next(chars) != '(':
		return ParseResult(False)
	forms = []
	while True:
		skip_whitespace(chars)
		if _lookahead1(')')(chars).success:
			break
		forms.append(parse_form(chars).result)
	return ParseResult(True, List(forms))


@_component_parser
def parse_comment(chars):
	if next(chars) != ';':
		return ParseResult(False)
	msg = []
	for c in chars:
		if c == '\n' or c == "":
			break
		msg.append(c)
	return ParseResult(True, Comment("".join(msg)))


@_component_parser
def parse_integer(chars):
	num_str = []
	c = next(chars)
	if c == '+' or c == '-':
		num_str.append(c)
		c = next(chars)

	if c not in _DIGITS:
		return ParseResult(False)
	num_str.append(c)

	for c in chars:
		if c not in _DIGITS:
			# Digits ended. Only accept as integer if we ended on a separator
			# (i.e., not in the middle of a weird identifier).
			if c not in _SEPARATORS:
				return ParseResult(False)
			break
		num_str.append(c)
	return ParseResult(True, Integer(int("".join(num_str))), -1)


@_component_parser
def parse_string(chars):
	if next(chars) != '"':
		return ParseResult(False)

	s = []
	for c in chars:
		if c == '"':
			break
		if c == '\\':  # escape
			c = next(chars)
		if c == "":
			raise ParseError("Unterminated string literal.")
		s.append(c)
	return ParseResult(True, String("".join(s)))


@_component_parser
def parse_symbol(chars):
	s = []
	for c in chars:
		if c not in _IDENT_CHARS:
			break
		s.append(c)
	if len(s) > 0:
		return ParseResult(True, Symbol("".join(s)), -1)
	return ParseResult(False)
