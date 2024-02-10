_str_trans = str.maketrans({
	'"': '\\"',
	"\\": "\\\\"
})

def form_to_str(form):
	match form:
		case ("SYM", symbol):
			return symbol
		case ("LIT", lit):
			if isinstance(lit, str):
				return '"' + lit.translate(_str_trans) + '"'
			return str(lit)
		case [*forms]:
			return "(" + " ".join(map(form_to_str, forms)) + ")"
		case str(s):
			return '"' + s.translate(_str_trans) + '"'
		case _:
			return str(form)
