#!/usr/bin/python3

import sys, re
import json

import fileinput

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
		
class myPyJSON :
	
	def __init__ (self) :
		self._jsonPattern = "^(([A-Za-z0-9]+\s*)+:\s*)?([{].*[}])\s*$"
		self._jsonText = [ ]
		
	@property
	def pattern (self) :
		return self._jsonPattern
	
	@property
	def json (self) :
		bag = [ ]		
		for line in self._jsonText :
			ref = re.match(self.pattern, line)
			if ref :
				bag.append(ref[3])
		return bag
	
	@property
	def data (self) :
		return [ json.loads(marble) for marble in self.json ]
	
	@property
	def allData (self) :
		hashtable = { }
		for table in self.data :
			hashtable = {**hashtable, **table}
		return hashtable
		
	def accept (self, jsonSource) :
		if isinstance(jsonSource, str) :
			src = jsonSource.split("\n")
		else :
			src = jsonSource		
		
		jsonMatches = [ re.match(self.pattern, line) for line in src ]
		self._jsonText = [ ref[3] for ref in jsonMatches if ref ]
	
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
	
	print("Good JSON...")
	
	table1 = {"Ingest Title": "Alabama Department of Archives and History WPA Folder 01", "File Size ": "2.1G (2,243,154,758 bytes, 689 files)", "Plugin JAR": "http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar", "Plugin ID": "gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin", "Plugin Name": "Alabama Department of Archives and History Directory Plugin", "Plugin Version": "1", "Start URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "Manifest URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "Base URL": "base_url=\"http://archives.alabama.gov/Lockss/\"", "Subdirectory": "subdirectory=\"WPA-Folder-01\"", "au_name": "Alabama Department of Archives and History Directory Plugin, Base URL http://archives.alabama.gov/Lockss/, Subdirectory WPA-Folder-01"}
	table2 = {"au_start_url": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "au_manifest": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "parameters": [["base_url", "http://archives.alabama.gov/Lockss/"], ["subdirectory", "WPA-Folder-01"]]}

	inp = "USELESS LINE: FooBar" + "\n" + "JSON PACKET: " + json.dumps(table1) + "\n" + json.dumps(table2) + "\n\n"

	jsonInput = myPyJSON()
	jsonInput.accept(inp)
	print("")
	
	print("")
	print("JSON TEXT >>>")
	print(jsonInput.json)
	print("")
	print("JSON DATA >>>")
	print(jsonInput.data)
	print("")
	print("AGGREGATED JSON DATA >>>")
	print(jsonInput.allData)
	print("")
	
	print("Bad JSON...")

	inp = "JSON PACKET: {oooOOooo what's this?}" + "\n" + "NON-JSON LINE: Hmmm"

	jsonInput = myPyJSON()
	jsonInput.accept(inp)
	print("")
	
	print("")
	print("JSON TEXT >>>")
	print(jsonInput.json)
	print("")
	print("JSON DATA >>>")
	try :
		print(jsonInput.data)
	except json.decoder.JSONDecodeError as e :
		print("myPyJSON.data -- excepted expected, OK !")
	print("")
	print("AGGREGATED JSON DATA >>>")
	try :
		print(jsonInput.allData)
	except json.decoder.JSONDecodeError as e :
		print("myPyJSON.data -- excepted expected, OK !")
	print("")
