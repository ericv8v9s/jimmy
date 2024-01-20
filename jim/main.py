from jim import reader, interpreter


def main(argv):
	if len(argv) == 1:
		repl()
	elif len(argv) == 2:
		fname = argv[1]
		if fname == "-":
			fname = "/dev/stdin"
		with open(fname) as f:
			for form in reader.feed(f.read()):
				interpreter.evaluate(form)
	else:
		print(f"Usage: {argv[0]} [file]")


def repl():
	while True:
		try:
			line = input("IN: ")
		except EOFError:
			return

		for form in reader.feed(line):
			result = interpreter.evaluate(form)
			print("OUT: ", result)


if __name__ == "__main__":
	import sys
	main(sys.argv)
