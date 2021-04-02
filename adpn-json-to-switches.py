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

	def display_usage (self) :
		print(self.__doc__)

	def execute (self) :
		try :
			jsonInput = myPyJSON(splat=True, cascade=True)
			lineinput = [ line for line in fileinput.input() ]
			jsonInput.accept(lineinput)
			try :
				table = jsonInput.allData
			except json.decoder.JSONDecodeError as e:
				jsonInput.accept( lineinput, screen=True )
				table = jsonInput.allData
	
			if ('Ingest Title' in table) :
				print('--au_title=%(name)s' % {"name": table['Ingest Title']})

			if ('Plugin JAR' in table) :
				print('--jar=%(url)s' % {"url": table['Plugin JAR']})
			if ('jar' in table) :
				print('--jar=%(url)s' % {"url": table['jar']})
			if ('Plugin ID' in table) :
				print('--plugin-id=%(id)s' % {"id": table['Plugin ID']})
			elif ('Plugin Name' in table) :
				print('--plugin=%(name)s' % {"name": table['Plugin Name']})

			if ('File Size' in table or 'File Size ' in table) :
				strSize = table.get('File Size','') + table.get('File Size ','')
				print('--file-size=%(size)s' % {"size": strSize})
			
			if ('local' in table) :
				print('--local=%(dir)s' % {"dir": table['local']})

			if ('staged' in table) :
				print('--staged=%(ftp)s' % {"ftp": table['staged']})
			
			if ('From Peer' in table) :
				print('--peer-from=%(peer)s' % {"peer": table.get('From Peer')})
				
			if ('To Peer' in table) :
				print('--peer-to=%(peer)s' % {"peer": table.get('To Peer')})
				
			if ('Ingest Report' in table) :
				print('--ingest-report=%(report)s' % {"report": table.get('Ingest Report')})
				
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

	(sys.argv, switches) = myPyCommandLine(sys.argv).parse()
	
	exitcode = 0
	script = ADPNJSONToSwitches(scriptname, switches)
	if script.switched('help') :
		script.display_usage()
	else :
		script.execute()
	sys.exit(script.exitcode)

		