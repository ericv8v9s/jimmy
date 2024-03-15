from jim import interpreter, checker


def print_usage():
	import sys
	print(f"Usage: {sys.argv[0]} [run filename]\n"
	      f"    OR {sys.argv[0]} check filename")


def main(argv):
	match argv:
		case [name]:
			interpreter.main([])
		case [name, "run", *rest]:
			interpreter.main(rest)
		case [name, "check", *rest]:
			checker.main(rest)
		case [name, *args]:
			print_usage()
		case _:
			assert False
