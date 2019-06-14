#!/usr/bin/python3

import sys, re


class myPyCommandLine :

	def __init__ (self, argv: list = [], defaults: dict = {}) :
		self._argv = argv
		self._switches = {}
		self._defaults = defaults
		self._switchPattern = '--([0-9_A-z][^=]*)(\s*=(.*)\s*)?$'

	@property 
	def pattern (self) :
		return self._switchPattern

	def argv (self) :
		return self._argv
	
	def switches (self) :
		return self._switches
		
	def KeyValuePair (self, switch) :
		ref=re.match(self.pattern, switch)
	
		key = ref[1]
		if ref[3] is None :
			value = ref[1]
		else :
			value = ref[3]
	
		return (key, value)

	def parse (self, argv: list = [], defaults: dict = {}) -> tuple :
		if len(argv) > 0 :
			the_argv = argv
		else :
			the_argv = self.argv()
		
		switches = dict([ self.KeyValuePair(arg) for arg in the_argv if re.match(self.pattern, arg) ])
		switches = {**self._defaults, **defaults, **switches}

		argv = [ arg for arg in the_argv if not re.match(self.pattern, arg) ]
		
		self._argv = argv
		self._switches = switches
		
		return (argv, switches)
		
	
if __name__ == '__main__':

	defaults = {"foo": "bar"}
	ss = {}
	
	old_argv = sys.argv

	print("DEFAULTS: ", "\t", defaults)
	print("")
	
	print(">>>", "(sys.argv, sw) = myPyCommandLine(sys.argv).parse(defaults=defaults)")
	(sys.argv, sw) = myPyCommandLine(sys.argv).parse(defaults=defaults)

	print("ARGV:    ", "\t", sys.argv)
	print("SWITCHES:", "\t", sw)

	sys.argv = old_argv
	
	print("")
	
	print(">>>", "cmd = myPyCommandLine(sys.argv) ; cmd.parse(defaults=defaults) ; args = cmd.argv() ; sw = cmd.switches()")

	cmd = myPyCommandLine(sys.argv)
	cmd.parse(defaults=defaults)
	args = cmd.argv()
	sw = cmd.switches()
	
	print("ARGS:    ", "\t", args)
	print("SWITCHES:", "\t", sw)
	
	sys.argv = old_argv

	print("")
	