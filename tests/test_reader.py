from jim.reader import *
from jim.ast import *
import pytest


def dummy_io(string):
	"""
	Returns a generator that produces character from the string one at a time
	then yields empty strings.
	"""
	for c in string:
		yield c
	while True:
		yield ""


class DummyResult:
	def __init__(self,
			success: bool,
			result: Any = None,
			chars_consumed_adj: int = None):
		self.success = success
		self.result = result
		self.chars_consumed_adj = chars_consumed_adj

	def __eq__(self, other: ParseResult):
		if self.success != other.success:
			return False
		elif not self.success:
			# We expect a failure and ParseResult reports a failure,
			# don't bother to check further.
			return True
		return (self.result == other.result
				and (self.chars_consumed_adj == other.chars_consumed_adj
					if self.chars_consumed_adj is not None else True))


def good(result, adj=None):
	return DummyResult(True, result, adj)

def bad():
	return DummyResult(False)


def test_parse_string():
	assert good(String("hello")) == parse_string(dummy_io('"hello"'))
	assert good(String("")) == parse_string(dummy_io('""'))
	assert good(String('string "with" escapes'))  \
			== parse_string(dummy_io(r'"string \"with\" escapes"'))

	assert bad() == parse_string(dummy_io('not a string'))
	assert bad() == parse_string(dummy_io('42'))
	assert bad() == parse_string(dummy_io('missing open"'))

	with pytest.raises(ParseError):
		parse_string(dummy_io('"not closed'))
	with pytest.raises(ParseError):
		parse_string(dummy_io('"'))


def test_parse_int():
	assert good(Integer(0)) == parse_integer(dummy_io('0'))
	assert good(Integer(-5)) == parse_integer(dummy_io('-5'))
	assert good(Integer(42)) == parse_integer(dummy_io('42'))
	assert good(Integer(42)) == parse_integer(dummy_io('+42'))

	assert bad() == parse_integer(dummy_io('hello'))
	assert bad() == parse_integer(dummy_io('"a string"'))


def test_parse_symbol():
	assert good(Symbol("hello")) == parse_symbol(dummy_io("hello"))
	# A number can indeed get parsed as a symbol:
	# this is controlled by parse_form where parse_integer is attempted first.
	assert good(Symbol("8")) == parse_symbol(dummy_io("8"))

	assert bad() == parse_symbol(dummy_io('"a string"'))
	assert bad() == parse_symbol(dummy_io(""))


def test_parse_comment():
	assert good(Comment("hello")) == parse_comment(dummy_io(";hello"))
	assert good(Comment("")) == parse_comment(dummy_io(";"))
	assert bad() == parse_comment(dummy_io("8"))
	assert bad() == parse_comment(dummy_io("hi"))
	assert bad() == parse_comment(dummy_io(""))
