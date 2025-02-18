if __debug__:
	from sys import stderr
	def debug(*args, **kws):
		kws.setdefault("file", stderr)
		print("[DEBUG]", *args, **kws)
else:
	def debug(*args, **kws):
		pass
