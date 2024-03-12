from jim import reader, interpreter
import sys


def main(argv):
	if len(argv) == 1:
		repl()
	elif len(argv) == 2:
		run_file(argv[1])
	else:
		print(f"Usage: {argv[0]} [file]")


def repl():
	while True:
		print("IN: ", end="", flush=True)

		try:
			parsed = reader.parse(lambda: sys.stdin.read(1))
		except reader.ParseError as e:
			print(str(e), file=sys.stderr)
			break

		if parsed is None:
			break

		result = interpreter.top_level_evaluate(parsed)
		if result is not None:
			print("OUT:", result, flush=True)


def run_file(fname):
	if fname == "-":
		f = sys.stdin
	else:
		f = open(fname)
	with f:
		while True:
			try:
				form = reader.parse(lambda: f.read(1))
			except reader.ParseError as e:
				print(str(e), file=sys.stderr)
				break
			if form is None:
				break
			interpreter.top_level_evaluate(form)


if __name__ == "__main__":
	main(sys.argv)
