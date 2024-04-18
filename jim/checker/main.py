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
				proof_correct = True
				while proof_correct:
					try:
						form = reader.parse(lambda: f.read(1))
						if form is None:
							break
						else:
							proof_correct = top_level_evaluate(form)
					except reader.ParseError as e:
						print(str(e), file=sys.stderr)
						proof_correct = False

				if proof_correct:
					print("Proof is valid.")
				else:
					print("PROOF FAILED")

		case _:
			main.print_usage()
