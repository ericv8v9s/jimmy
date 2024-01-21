from jim import reader, interpreter
from sys import stdin, stdout


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
		print("IN: ", end="")
		stdout.flush()
		parsed = reader.parse(read_char)
		if parsed is None:
			print()
			break
		print("OUT:", interpreter.evaluate(parsed))
		stdout.flush()


def run_file(fname):
	if fname == "-":
		f = stdin
	else:
		f = open(fname)
	with f:
		while True:
			form = reader.parse(lambda: f.read(1))
			print(interpreter.evaluate(form))
			if form is None:
				break


if __name__ == "__main__":
	import sys
	main(sys.argv)
