def main(argv):
	import sys
	from jim import reader, main
	from .interpreter import evaluate
	from .errors import JimmyError, format_error

	match argv:
		case []:  # interactive mode
			while True:
				print("<- ", end="", flush=True)

				try:
					parsed = reader.parse(lambda: sys.stdin.read(1))
				except reader.ParseError as e:
					print(str(e), file=sys.stderr)
					break

				if parsed is None:
					break

				try:
					result = evaluate(parsed)
					# None is produced when the input was a no-op (e.g., a comment).
					if result is not None:
						print("->", result, flush=True)
				except JimmyError as e:
					print(format_error(e), file=sys.stderr)

		case [filename]:
			if filename == "-":
				f = sys.stdin
			else:
				f = open(filename)
			with f:
				while True:
					try:
						form = reader.parse(lambda: f.read(1))
					except reader.ParseError as e:
						print(str(e), file=sys.stderr)
						break
					if form is None:
						break
					#print("REPROD:", str(form).rstrip())
					evaluate(form)

		case _:
			main.print_usage()
