#!/usr/bin/python3
#
# adpn-json-to-switches.py: utility script, pulls data elements from a JSON hash table
# provided on stdin and outputs the value (a printed str or a serialized str equivalent)
# from a given key-value pair, so that bash scripts can capture values from JSON packets.
#
# @version 2021.0401

import sys
import os.path
import fileinput
import re
import json
import urllib.parse
from myLockssScripts import myPyCommandLine, myPyJSON

class ADPNJSONToSwitches :
	"""
Usage: VALUE=$( <INPUT> | adpn-json.py - --key=<KEY> )

Input: a copy-pasted block of text, including one or more JSON hash tables,
possibly prefixed by a label like "JSON PACKET: " before the beginning of
the {...} hash table structure. (The label will be ignored.) If there are
multiple lines with JSON hash tables in them, the divers hash tables will
be merged together into one big hash table.

Output: the str value or typecasted str serialization of the value paired
with the provided key in the hash table. If there is no such key in the
hash table, nothing is printed out.

Exit code:
0= successful output of the value associated with the key requested
1= failed to output a value because the key requested does not exist
2= failed to output a value because the JSON could not be decoded
	"""
	
	def __init__ (self, scriptname, argv, switches) :
		self.scriptname = scriptname
		self._argv = argv
		self._switches = switches
		self._output = []
		self._flags = { "json_error": [], "key_error": [], "nothing_found": [], "output_error": [] }
		
	@property
	def switches (self) :
		return self._switches

	@property
	def flags (self) :
		return self._flags
		
	@property
	def argv (self) :
		return self._argv

	@property
	def output (self) :
		return self._output
		
	def switched (self, name, default = None) :
		result = default
		if name in self.switches :
			result = self.switches[name]
		return result

	def add_flag (self, flag, value) :
		if value is not None :
			self.flags[flag].extend( [ value ] )

	def test_flagged (self, flag) :
		flags = self.flags[flag]
		return (len(flags) > 0)	

	def get_exitcode (self) :
		if self.test_flagged("json_error") :
			exitcode=2
		elif self.test_flagged("key_error") :
			exitcode=1
		elif self.test_flagged("output_error") :
			exitcode=254
		else :
			exitcode=0
		return exitcode
		
	def display_usage (self) :
		print(self.__doc__)

	def wants_table(self) :
		return (( self.switches.get('key') is None ) or ( self.get_output_format(index=1) == "table" ))
	
	def is_multiline_output (self, output=None) :
		out = ( self.output ) if output is None else ( output )
		return ( len(out) > 1 )
	
	def get_output_terminator (self, output=None) :
		terminal="\n" if ( self.wants_table() or self.is_multiline_output(output) ) else ""
		return terminal
		
	def get_output_format (self, index=0) :
		sSpec = self.switches.get('output') if self.switches.get('output') is not None else "text/plain"
		aSpec = sSpec.split(";")
		return aSpec[index] if (index<len(aSpec)) else None
		
	def add_output (self, value, key=None, pair=False, table={}, context={}) :
		out = self.get_output(value, key, pair, table, context)

		if isinstance(out, list) :
			self.output.extend( out )
		else :
			self.add_flag("output_error", out )
			
	def get_output (self, value, key=None, pair=False, table={}, context={}) :
		lines = []
		if ( self.get_output_format() == 'urlencode' or self.get_output_format() == "multipart/form-data" ) :
			display_value = urllib.parse.quote(str(value))
		else :
			display_value = str(value)
			
		if (pair) :
			lines.extend([ "%(key)s\t%(value)s" % {"key": key, "value": display_value}])
		else :
			lines.extend([ display_value ])
				
		return lines
		
	def display_data_dict (self, table, context, parse) :
		keys = ( self.switches.get('key').split(":") ) if self.switches.get('key') is not None else table.keys()
		out = []
		paired=( self.wants_table() or (len(keys) > 1) )
		try :
			for key in keys :
				out.extend( self.get_output(table[key], key, pair=paired, table=table, context=context ) )
		except KeyError as e :
			self.add_flag("key_error", key)

		if self.wants_table() or isinstance(context, list) :
			line = "\t".join(out)
			self.output.extend([ line ])
		else :
			self.output.extend(out)
			
	def display_data_list (self, table, context, parse) :
		i = 0
		for item in table :
			where = ( self.switches.get('where').split(":", 1) if self.switches.get("where") is not None else [] )
			matched = True
			if len(where) == 2 :
				key=where[0]
				value=where[1]
				if isinstance(item[key], str ) :
					matched = ( item[key] == value )
				elif isinstance(item[key], int ) :
					matched = ( item[key] == int(value) )
						
			if matched :
				if parse :
					self.display_data(item, context, 0)
				else :
					self.add_output(item, table=table, context=context)
				i = i + 1

	def display_data (self, table, context, parse) :
		if ( isinstance(table, dict) ) :
			self.display_data_dict(table, context, parse)
		elif ( isinstance(table, list) ) :
			self.display_data_list(table, context, parse)
		else :
			self.add_output(item, table=table, context=context)
			
	def execute (self) :
		try :
			jsonInput = myPyJSON()
			jsonInput.accept([ line for line in fileinput.input() ])
			table = jsonInput.allData
			
			self.display_data(table, table, self.switches.get('parse'))
			if len(self.output) > 0 :
				print("\n".join(self.output), end=self.get_output_terminator())
				
		except json.decoder.JSONDecodeError as e :
	
			self.add_flag("json_error", "\n".join(jsonInput.text))
		
		for err in self.flags["json_error"] :
			print(
				("[%(script)s] JSON encoding error. Could not extract data or key-value pairs from "
					+ "the provided data: '%(json)s'")
					% {"script": self.scriptname, "json": err.strip()},
				file=sys.stderr
			)
				
if __name__ == '__main__' :

	scriptname = sys.argv[0]
	scriptname = os.path.basename(scriptname)

	(sys.argv, switches) = myPyCommandLine(sys.argv).parse()
	
	script = ADPNJSONToSwitches(scriptname, sys.argv, switches)
	if script.switched('help') :
		script.display_usage()
	else :
		script.execute()
	sys.exit(script.get_exitcode())

		