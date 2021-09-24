#!/usr/bin/python3
#
# adpn-json-to-switches.py: utility script, converts data from a JSON hash table provided
# on stdin to switches used by adpn-ingest-test and related scripts.
#
# @version 2021.0402

import sys
import os.path
import fileinput
import re
import json
from myLockssScripts import myPyCommandLine, myPyJSON

class ADPNJSONToSwitches :
	"""
Usage: <INPUT> | adpn-json-to-switches.py -

Input: a copy-pasted block of text, including one or more JSON hash tables,
possibly prefixed by a label like "JSON PACKET: " before the beginning of
the {...} hash table structure. (The label will be ignored.) If there are
multiple lines with JSON hash tables in them, the divers hash tables will
be merged together into one big hash table.

Output: a series of command-line switches, in --<KEY>=<VALUE> format.
Written to stdout, one switch per line. For example:

	--au_title=WPA Folder 01
 	--jar=http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar
 	--plugin-id=gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin
 	--remote=1
 	--subdirectory=WPA-Folder-01
	"""
	
	def __init__ (self, scriptname, switches) :
		self.exitcode = 0
		self.scriptname = scriptname
		self._switches = switches
		
	@property
	def switches (self) :
		return self._switches
	
	def switched (self, name, default = None) :
		result = default
		if name in self.switches :
			result = self.switches[name]
		return result
	
	@property
	def key_mappings (self) :
		return {
			"Ingest Title": "au_title",
			"Plugin JAR": "jar",
			"jar": "jar",
			"Plugin ID": "plugin-id",
			"File Size": "file-size",
			"File Size ": "file-size",
			"local": "local",
			"staged": "staged",
			"Plugin Name": "plugin",
			"From Peer": "peer-from",
			"To Peer": "peer-to",
			"Ingest Report": "ingest-report",
			"Staged To": "staged-to",
			"Staged By": "staged-by",
			"Verified By": "verified-by",
			"Packaged In": "packaged-in",
			"Packaged By": "packaged-by",
			"Gitlab Issue": "gitlab-issue",
			"Gitlab Resource": "gitlab-resource",
			"adpn:workflow": "adpn:workflow"
		}
		
	def key_to_switch (self, key, value=None) :
		switch_value=( value if value is not None else table.get(key) )
		
	def display_usage (self) :
		print(self.__doc__)

	def execute (self) :
		if self.switched('reverse') :
			self.write_tsv_from_switches()
		else :
			self.write_switches_from_json()
	
	def write_key_value_from_switch (self, switch, key, value, table) :
		if value is None :
			pass
		elif type(value) is list :
			for item in value :
				self.write_key_value_from_switch(switch, key, item, table)
		else :
			print( "\t".join( [ key, value ] ) )
		table[switch] = None # Do this once only
	
	def write_tsv_from_switches (self) :
		to_print = { **self.switches }
		for (key, switch) in self.key_mappings.items() :
			self.write_key_value_from_switch(switch, key, to_print.get(switch), to_print)
	
	def write_switch_from_key_value (self, key, value, switch=None) :
		switch_name = switch if switch is not None else key
		sw = None
		if value is not None :
			if type(value) is bool :
				sw = ('--%(sw)s' % { "sw": switch_name }) if value else None
			elif type(value) is int :
				sw = ('--%(sw)s=%(v)d' % { "sw": switch_name, "v": value })
			elif type(value) is float :
				sw = ('--%(sw)s=%(v)f' % { "sw": switch_name, "v": value })
			elif type(value) is list :
				for item in value :
					self.write_switch_from_key_value(key, item)
			else :
				sw = ('--%(sw)s=%(v)s' % { "sw": switch_name, "v": str(value) })
		if sw is not None :
			print(sw)
	
	def write_switches_from_json (self) :
		try :
			jsonInput = myPyJSON(splat=True, cascade=True)
			lineinput = [ line for line in fileinput.input() ]
			jsonInput.accept(lineinput)
			try :
				table = jsonInput.allData
			except json.decoder.JSONDecodeError as e:
				jsonInput.accept( lineinput, screen=True )
				table = jsonInput.allData
			
			for (key, switch) in self.key_mappings.items() :
				value = table.get(key)
				self.write_switch_from_key_value(key, value, switch)
			
			if ('parameters' in table) :
				if len(table) > 0 :
					for param, value in table['parameters'] :
						print('--%(KEY)s=%(VALUE)s' % {"KEY": param, "VALUE": value})
		except KeyboardInterrupt as e :

			print(
				("[%(script)s] JSON input aborted by user keyboard break (Ctrl-C); no data decoded.")
				% {"script": self.scriptname},
				file=sys.stderr
			)
			self.exitcode = 255
		
		except BrokenPipeError as e :
		
			print(
				("[%(script)s] JSON input aborted by broken pipe; no data decoded.")
				% {"script": self.scriptname},
				file=sys.stderr
			)
			self.exitcode = 255
			
		except FileNotFoundError as e: 
		
			print(
				("[%(script)s] JSON input file [%(file)s] not found; no data decoded.")
				% {"script": self.scriptname, "file": e.filename},
				file=sys.stderr
			)
			self.exitcode = 2
		
		except PermissionError as e: 
		
			print(
				("[%(script)s] JSON input file [%(file)s] may not be read (permissions error); no data decoded.")
				% {"script": self.scriptname, "file": e.filename},
				file=sys.stderr
			)
			self.exitcode = 3
			
		except IsADirectoryError as e: 

			print(
				("[%(script)s] JSON input cannot be read from a directory [%(file)s]; no data decoded.")
				% {"script": self.scriptname, "file": e.filename},
				file=sys.stderr
			)
			self.exitcode = 4

		except json.decoder.JSONDecodeError as e :
	
			print(
				("[%(script)s] JSON encoding error. Could not extract key-value pairs from "
				+ "the provided data:\n\n%(json)s")
				% {"script": self.scriptname, "json": jsonInput.raw},
				file=sys.stderr
			)
			self.exitcode = 1
	
if __name__ == '__main__' :

	scriptname = sys.argv[0]
	scriptname = os.path.basename(scriptname)

	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={ "adpn:workflow": [] }).parse()
	
	exitcode = 0
	script = ADPNJSONToSwitches(scriptname, switches)
	if script.switched('help') :
		script.display_usage()
	else :
		script.execute()
	sys.exit(script.exitcode)

		