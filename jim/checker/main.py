def main(argv):
	import sys
	from jim import reader, main
	from .interpreter import top_level_evaluate

	match argv:
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
					top_level_evaluate(form)

		case _:
			main.print_usage()
