from jim import reader, interpreter, utils
from sys import stdin


def main(argv):
	if len(argv) == 1:
		repl()
	elif len(argv) == 2:
		run_file(argv[1])
	else:
		print(f"Usage: {argv[0]} [file]")


def repl():
	read_char = lambda: stdin.read(1)
	while True:
		print("IN: ", end="", flush=True)

		try:
			parsed = reader.parse(read_char)
		except reader.ParseError as e:
			print(str(e))
			continue
		if parsed is None:
			break

		result = interpreter.top_level_evaluate(parsed)
		if result is not None:
			print("OUT:", utils.form_to_str(result), flush=True)


def run_file(fname):
	if fname == "-":
		f = stdin
	else:
		f = open(fname)
	with f:
		while True:
			try:
				form = reader.parse(lambda: f.read(1))
			except reader.ParseError as e:
				print(str(e))
				break
			if form is None:
				break

			if interpreter.top_level_evaluate(form) is None:
				break


if __name__ == "__main__":
	import sys
	main(sys.argv)
