if __debug__:
	from sys import stderr
	def debug(*args, **kws):
		kws.setdefault("file", stderr)
		print(*args, **kws)
else:
	def debug(msg, **kws):
		pass
