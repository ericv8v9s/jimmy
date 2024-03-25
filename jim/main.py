from jim import executor, checker


def print_usage():
	import sys
	print(f"Usage: {sys.argv[0]} [run filename]\n"
	      f"    OR {sys.argv[0]} check filename")


def main(argv):
	match argv:
		case [name]:
			executor.main([])
		case [name, "run", *rest]:
			executor.main(rest)
		case [name, "check", *rest]:
			checker.main(rest)
		case [name, *args]:
			print_usage()
		case _:
			assert False
