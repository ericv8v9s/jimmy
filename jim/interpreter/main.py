from .evaluator import evaluate
from .builtin import builtin_symbols
from jim import reader
from jim.evaluator.evaluator import init_context
from jim.evaluator.errors import JimmyError, format_error
import sys


def main(argv):
	context = init_context(builtin_symbols)

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
					result = evaluate(form, context)
					if result is not None:
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
						evaluate(form, context)
				except reader.ParseError as e:
					print(str(e), file=sys.stderr)
				except JimmyError as e:
					print(format_error(e), file=sys.stderr)

		case _:
			import jim.main
			jim.main.print_usage()
