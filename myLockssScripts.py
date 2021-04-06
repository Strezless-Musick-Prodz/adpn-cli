#!/usr/bin/python3
#
# myLockssScripts: utility classes for use across various ADPNet/LOCKSS automation scripts
# Regularizing the use of key-value pair switches, JSON input, etc.
#
# @version 2019.0624

import sys
import re
import json
import fileinput
import subprocess
from subprocess import PIPE

class myPyPipeline :
	"""Given a sequence of shell processes, pipe output from one to input for the next, using POSIX pipes.
	
	@param iterable pipeline an iterable sequence of lists specifying shell commands with command-line parameters
	"""
	def __init__ (self, pipeline) :
		self.pipeline = pipeline
	
	def process (self, cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, encoding="utf-8") :
		if callable(cmd) :
			res=cmd(stdin=stdin, stdout=stdout, stderr=stderr, encoding=encoding)
		else :
			res=subprocess.Popen(cmd, stdin=stdin, stdout=stdout, stderr=stderr, encoding=encoding)
		return res
		
	def siphon (self, encoding="utf-8") :
		processes = []
		_stdin = sys.stdin
		for cmd in self.pipeline :
			proc = self.process(cmd=cmd, stdin=_stdin, stdout=PIPE, encoding=encoding)
			_stdin = proc.stdout
			processes.append(proc)
		
		_lastproc = None
		for proc in processes :
			if _lastproc is not None :
				_lastproc.stdout.close()
			_lastproc = proc
		
		(buf, errbuf) = _lastproc.communicate()
		_lastproc.stdout.close()
		
		return (buf, errbuf, [proc.returncode for proc in processes])
	
class myPyCommandLine :
	"""Parse a Unix-style shell command-line, separating out configuration parameters and files/objects.
	"""
	
	def __init__ (self, argv: list = [], defaults: dict = {}, configfile: str = "", settingsgroup = "") :
		"""Initialize with a list of command-line arguments, and optionally a dictionary of default values for expected configuration switches."""
		self._argv = argv
		self._switches = {}
		
		jsonText = "{}"
		if len(configfile) > 0 :
			try :
				default_map = open(configfile, "r")
				jsonText = "".join([line for line in default_map])
				default_map.close()
			except FileNotFoundError as e :
				jsonText = "{}"
				
		try :
			self._defaults = {**defaults, **json.loads(jsonText)}
		except json.decoder.JSONDecodeError as e :
			self._defaults = defaults
		
		if len(settingsgroup) > 0 :
			overlay = { }

			if not isinstance(settingsgroup, list) :
				settingsgroup = [ settingsgroup ]

			for key in self._defaults.keys() :
				subkey = key.split("/", maxsplit=2)
				if len(subkey) > 1 and settingsgroup.count(subkey[0]) > 0 :
					overlay[subkey[1]] = self._defaults[key]
			
			self._defaults = {**self._defaults, **overlay}
			
		self._switchPattern = '--([0-9_A-z][^=]*)(\s*=(.*)\s*)?$'

	@property 
	def pattern (self) -> str :
		"""Provides a regex that matches a command-line switch and parse out switch names and values."""
		return self._switchPattern

	@property
	def argv (self) -> list :
		"""List of files and objects from the command line, without --switches.
		"""
		return self._argv
	
	@property
	def switches (self) -> dict :
		"""Dictionary of configuration switches provided on command-line or in defaults.
		"""
		return self._switches
		
	def KeyValuePair (self, switch) -> tuple :
		"""Parses a string command-line switch into a (key, value) pair.

		Switches may be a parameter name and value (e.g. '--output=html' -> ('output', 'html')
		or they may be a simple setting name (e.g. '--turned-on' -> ('turned-on', 'turned-on')
		"""
		ref=re.match(self.pattern, switch)
	
		key = ref.group(1)
		if ref.group(3) is None :
			value = ref.group(1)
		else :
			value = ref.group(3)
	
		return (key, value)

	def parse (self, argv: list = [], defaults: dict = {}) -> tuple :
		"""Separate out a list of command-line arguments into switches and files/objects.
		"""
		if len(argv) > 0 :
			the_argv = argv
		else :
			the_argv = self.argv
		
		switches = dict([ self.KeyValuePair(arg) for arg in the_argv if re.match(self.pattern, arg) ])
		switches = {**self._defaults, **defaults, **switches}

		argv = [ arg for arg in the_argv if not re.match(self.pattern, arg) ]
		
		self._argv = argv
		self._switches = switches
		
		return (argv, switches)
	
	def compose (self, keyvalues: list) -> list :		
		return self.argv + [ "--%(k)s=%(v)s" % {"k": key, "v": value} for key, value in keyvalues if not value is None ]
		

class myPyJSON :
	"""Extract JSON hash tables from plain-text input, for example copy-pasted or piped into stdin.
	"""
	
	def __init__ (self, splat=True, cascade=False, where=None) :
		"""Initialize the JSON extractor pattern."""
		self._jsonProlog = r'^JSON(?:\s+(?:PACKET|DATA))?:\s*'
		self._jsonBraces = r'^\s*([{].*[}]|\[.*\])\s*'
		self._jsonRaw = ''
		self._jsonText = [ ]
		self._splat = splat
		self._cascade = cascade
		self.select_where(where)
		
	@property
	def prolog (self) :
		"""Regex that matches and parses out the JSON representation from a line of text."""
		return self._jsonProlog
	
	@property
	def braces (self) :
		"""Regex that matches and parses out a likely JSON hashtable or array from a line of text."""
		return self._jsonBraces
		
	@property
	def splat (self) :
		"""Switch for splatting (or not) single item lists into their first unit."""
		return self._splat
		
	@property
	def cascade (self) :
		"""Switch for joining (or not) multiple data items in a first-to-last cascade or list them separately."""
		return self._cascade
	
	@property
	def selected (self) :
		"""Lambda that filters JSON data objects according to programmatic criteria."""
		return self._where
	
	@property
	def raw (self) -> str :
		return self._jsonRaw

	@property
	def json (self) -> list :
		"""List of all the JSON representations taken from the accepted input."""
		return self._jsonText
	
	@property
	def data (self) -> "list of dict" :
		"""A list of all the hash tables parsed from the JSON representations."""
		return [ json.loads(marble) for marble in self.json ]
	
	@property
	def text (self) :
		return self._jsonText
		
	@property
	def allData (self) :
		"""A unified hash table that either lists or merges together all the tables parsed from the JSON representations."""
		data = {
			"splat": { "used": False, "data": [ ] },
			"hashes": { "used": 0, "data": { } },
			"lists": { "used": 0, "data": [ ] }
		}
		
		for datum in self.data :
			if self.selected(datum) :
				if self.cascade :
					if isinstance(datum, dict) :
						data["hashes"]["data"] = {**data["hashes"]["data"], **datum}
						data["hashes"]["used"] = True
					elif isinstance(datum, list) :
						data["lists"]["data"].extend(datum)
						data["lists"]["used"] = True
				else :
					data["splat"]["used"] = True
					data["splat"]["data"].extend( [ datum ] )
			
		splat = [ self.splatted(data[glob]["data"]) for glob in data.keys() if data[glob]["used"] ]
		return self.splatted(splat)

	def select_where (self, condition=None) :
		self._where = condition if condition is not None else lambda x: True
		
	def splatted (self, data, force=False) :
		splat = data
		if force or self.splat :
			if isinstance(data, list) :
				if len(data) == 0 :
					splat = None
				elif len(data) == 1 :
					splat = data[0]
				else :
					splat = data

		return splat
	
	def add_prolog (self, line) :
		if re.match(self.prolog, line, flags=re.I) :
			output=line
		else :
			output=( "JSON: %(line)s" % { "line": line } )
		return output
		
	def is_acceptable (self, line) :
		is_prologged = re.match(self.prolog, line, flags=re.I)
		is_braces = False
		maybe_braces = re.match(self.braces, line, flags=re.I)
		if maybe_braces :
			try :
				json.loads(line)
				is_braces = True
			except json.decoder.JSONDecodeError as e :
				is_braces = False
		return ( is_prologged or is_braces )
		
	def accept (self, jsonSource, screen=False) :
		"""Accept the plain-text input containing one or more JSON hash tables within the text.
		
		jsonSource can be a string, or an iterable object that spits out lines of text
		(for example, flieinput.input()).
		"""
		self._jsonRaw = ( jsonSource if isinstance(jsonSource, str) else "\n".join(jsonSource) )

		if screen :
			if isinstance(jsonSource, str) :
				split_src = [ jsonSource ]
			else :
				split_src = jsonSource
			self._jsonText = [ self.add_prolog(bit) for bit in split_src if self.is_acceptable(bit) ]
		else :
			self._jsonText = jsonSource
		
		if isinstance(self._jsonText, str) :
			src = self._jsonText
		else :
			src = "\n".join(self._jsonText)

		split_src = re.split(self.prolog, src, flags=re.M)
		self._jsonText = [ bit for bit in split_src if len(bit.strip()) > 0 ]
		
		if len(self._jsonText) == 0 :
			self._jsonText = [ "".join(src) ]
			
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
	
	print(">>>", "cmd = myPyCommandLine(sys.argv) ; cmd.parse(defaults=defaults) ; args = cmd.argv ; sw = cmd.switches")

	cmd = myPyCommandLine(sys.argv)
	cmd.parse(defaults=defaults)
	args = cmd.argv
	sw = cmd.switches
	
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
