def print_usage():
	import sys
	print(f"Usage: {sys.argv[0]} [run [filename]]\n"
	      f"    OR {sys.argv[0]} check [filename]")


def main(argv):
	match argv:
		case [name]:
			from jim import interpreter
			interpreter.main([])
		case [name, "run", *rest]:
			from jim import interpreter
			interpreter.main(rest)
		case [name, "check", *rest]:
			from jim import checker
			checker.main(rest)
		case [name, *args]:
			print_usage()
		case _:
			assert False
