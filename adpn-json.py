#!/usr/bin/python3
#
# adpn-json-to-switches.py: utility script, converts data from a JSON hash table provided
# on stdin to switches used by adpn-ingest-test and related scripts.
#
# @version 2019.0624

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
	
	def __init__ (self, scriptname, argv, switches) :
		self.exitcode = 0
		self.scriptname = scriptname
		self._argv = argv
		self._switches = switches
		
	@property
	def switches (self) :
		return self._switches

	@property
	def argv (self) :
		return self._argv

	def switched (self, name, default = None) :
		result = default
		if name in self.switches :
			result = self.switches[name]
		return result

	def display_usage (self) :
		print(self.__doc__)

	def execute (self) :
		try :
			jsonInput = myPyJSON()
			jsonInput.accept(fileinput.input())
			table = jsonInput.allData

			try :
				print(table[self.switches.get('key', '')], end="")
				self.exitcode = 0
			except KeyError as e :
				self.exitcode = 1
			
		except json.decoder.JSONDecodeError as e :
	
			print(
				("[%(script)s] JSON encoding error. Could not extract key-value pairs from "
				+ "the provided data:\n\n%(json)s")
				% {"script": self.scriptname, "json": jsonInput},
				file=sys.stderr
			)
			self.exitcode = 1
	
if __name__ == '__main__' :

	scriptname = sys.argv[0]
	scriptname = os.path.basename(scriptname)

	(sys.argv, switches) = myPyCommandLine(sys.argv).parse()
	
	exitcode = 0
	script = ADPNJSONToSwitches(scriptname, sys.argv, switches)
	if script.switched('help') :
		script.display_usage()
	else :
		script.execute()
	sys.exit(script.exitcode)

		