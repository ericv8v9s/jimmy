if __debug__:
	from functools import wraps
	from sys import stderr
	def debug(*args, **kws):
		kws.setdefault("file", stderr)
		print("[DEBUG]", *args, **kws)

	def _format_item(kv):
		return f"{kv[0]}={kv[1]}"
	def _format_call(fn, args, kws):
		if len(kws) == 0:
			kws_str = ""
		else:
			kws_str = ", " + ", ".join(map(_format_item, kws.items()))
		return f"{fn.__name__}({', '.join(map(str, args))}{kws_str})"

	def trace_entry(fn):
		@wraps(fn)
		def _(*args, **kws):
			debug(f"CALL: {_format_call(fn, args, kws)}")
			return fn(*args, **kws)
		return _

	def trace_exit(fn):
		@wraps(fn)
		def _(*args, **kws):
			result = fn(*args, **kws)
			debug(f"RETN: {_format_call(fn, args, kws)} -> {result}")
			return result
		return _

else:
	def debug(*args, **kws):
		pass
	def trace_entry(fn):
		return fn
	def trace_exit(fn):
		return fn
