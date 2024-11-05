def main(argv):
	import sys
	from jim import reader, main
	from .interpreter import evaluate
	from .errors import JimmyError, format_error

	match argv:
		case []:  # interactive mode
			forms = reader.load_forms(lambda: sys.stdin.read(1))
			while True:
				print("<- ", end="", flush=True)
				try:
					form = next(forms)
				except reader.ParseError as e:
					print(str(e), file=sys.stderr)
					break
				except StopIteration:
					break

				try:
					result = evaluate(form)
					print("->", repr(result), flush=True)
				except JimmyError as e:
					print(format_error(e), file=sys.stderr)

		case [filename]:
			if filename == "-":
				f = sys.stdin
			else:
				f = open(filename)
			with f:
				try:
					for form in reader.load_forms(lambda: f.read(1)):
						#print("REPROD:", str(form).rstrip())
						evaluate(form)
				except reader.ParseError as e:
					print(str(e), file=sys.stderr)
				except JimmyError as e:
					print(format_error(e), file=sys.stderr)

		case _:
			main.print_usage()
