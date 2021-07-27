#!/usr/bin/python3
#
# adpn-json.py: utility script, pulls data elements from a JSON hash table
# provided on stdin and outputs the value (a printed str or a serialized str equivalent)
# from a given key-value pair, so that bash scripts can capture values from JSON packets.
#
# @version 2021.0525

import sys
import os.path
import fileinput
import re, json, codecs
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
		self._default_mime = "text/plain"
		with open(argv[0], 'r') as f :
			for line in f.readlines() :
				ref = re.search(r'^#\s*@version\s*(.*)\s*$', line)
				if ref :
					self._version = ref.group(1)
			f.close()

	@property
	def version (self) :
		return self._version
		
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
		
	def switched (self, name, just_present=False, default=None) :
		result = default
		if name in self.switches :
			result = self.switches.get(name)
		return ( result is not None ) if just_present else result

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
	
	def display_version (self) :
		print("%(script)s version %(version)s" % {"script": self.scriptname, "version": self.version})
	
	def display_usage (self) :
		print(self.__doc__)

	def wants_splat(self) :
		return ( self.switches.get('nosplat') is None )
	
	def wants_cascade(self) :
		return ( self.switches.get('cascade') is not None )
		
	def wants_table(self) :
		requested_table = (( self.get_output_format(index=0) == "text/tab-separated-values" ) or ( self.get_output_format(index=1) == "table" ))
		implies_table = (( self.switches.get('key') is None ) and ( self.get_output_format(index=0) is None )) 
		return implies_table or requested_table
	
	def wants_printf_output (self) :
		return (( self.get_output_format() == "text/plain" ) and ( self.switches.get('template') is not None ))
	
	def wants_json_output(self) :
		return (( self.get_output_format() == "json" ) or ( self.get_output_format() == "application/json" ) )
		
	def data_matches (self, item, key, value) :
		matched = True
		if isinstance(item, dict) :
			matched = False
			if isinstance(item.get(key), str ) :
				matched = ( item.get(key) == str(value) )
			elif isinstance(item.get(key), int ) :
				matched = ( item.get(key) == int(value) )
		return matched

	@property
	def selected (self) :
		ok = lambda x: True
		if self.switches.get("where") :
			(key,value)=self.switches.get('where').split(":", 1)		
			ok = lambda x: self.data_matches(x, key, value)
		return ok
	
	def is_multiline_output (self, output=None) :
		out = ( self.output ) if output is None else ( output )
		return ( len(out) > 1 )
	
	def get_output_terminator (self, output=None) :
		terminal="\n" if ( self.wants_table() or self.is_multiline_output(output) ) else ""
		return terminal
		
	def get_output_format (self, index=0) :
		sSpec = self.switches.get('output') if self.switches.get('output') is not None else self._default_mime
		aSpec = sSpec.split(";")
		return aSpec[index] if (index<len(aSpec)) else None
	
	def get_printf_template (self) :
		return self.switches.get('template')
	
	def add_output (self, value, key=None, pair=False, table={}, context={}) :
		out = self.get_output(value, key, pair, table, context)

		if isinstance(out, list) :
			self.output.extend( out )
		else :
			self.add_flag("output_error", out )
	
	def get_json_indent (self) :
		indent=None
		fmt=self.get_output_format(index=1)
		fmt=fmt if fmt is not None else ''
		if self.switches.get('indent') is not None :
			try :
				indent=int(self.switches.get('indent'))
			except ValueError as e:
				indent=str(self.switches.get('indent'))
		elif self.get_output_format(index=1)=='prettyprint' :
			indent=0
		elif re.match(r'^indent=(.*)$', fmt) :
			m=re.search(r'^indent=(.*)$', fmt)
			try :
				indent=int(m.group(1))
			except ValueError as e:
				indent=str(m.group(1))
		return indent
	
	def get_output (self, value, key=None, pair=False, table={}, context={}) :
		lines = []
		if ( self.get_output_format() == 'urlencode' or self.get_output_format() == "multipart/form-data" ) :
			sValue = str(value)
			display_value = urllib.parse.quote(sValue.encode("utf-8", "surrogatepass"))
		else :
			display_value = str(value)
			
		if (pair) :
			lines.extend([ "%(key)s\t%(value)s" % {"key": key, "value": display_value}])
		else :
			lines.extend([ display_value ])
				
		return lines
	
	def display_templated_text (self, text, table) :
		data = table
		data["$n"] = "\n"
		data["$t"] = "\t"
		
		# Here is an ugly but functional way to process backslash escapes in the template
		# via <https://stackoverflow.com/questions/4020539/process-escape-sequences-in-a-string-in-python/37059682#37059682>
		text_template = codecs.escape_decode(bytes(text, "utf-8"))[0].decode("utf-8")
		
		result = ( text_template % table )
		return result
	
	def display_data_dict (self, table, context, parse, depth=0) :
		keys = ( self.switches.get('key').split(":") ) if self.switches.get('key') is not None else table.keys()
		out = {} if self.wants_json_output() else []
		paired=( self.wants_table() or (len(keys) > 1) )
		try :
			for key in keys :
				if self.wants_json_output() :
					out[key] = table[key]
				else :
					out.extend( self.get_output(table[key], key, pair=paired, table=table, context=context ) )
		except KeyError as e :
			self.add_flag("key_error", key)
		
		if self.wants_printf_output() :
			try :
				text = self.display_templated_text(self.get_printf_template(), table)
				self.output.append(text);
			except KeyError as e :
				self.add_flag("key_error", key)
		elif self.wants_json_output() :
			self.output.extend([ json.dumps(out,indent=self.get_json_indent()) ])
		elif self.wants_table() or isinstance(context, list) :
			line = "\t".join(out)
			self.output.extend([ line ])
		else :
			self.output.extend(out)
			
	def display_data_list (self, table, context, parse, depth=0) :
		i = 0
		for item in table :
			if self.selected(item) :
				if parse :
					self.display_data(item, context, 0, depth=depth+1)
				else :
					self.add_output(item, table=table, context=context)
				i = i + 1

	def display_data (self, table, context, parse, depth=0) :
		if ( isinstance(table, dict) ) :
			self.display_data_dict(table, context, parse, depth=depth+1)
		elif ( isinstance(table, list) ) :
			self.display_data_list(table, context, parse, depth=depth+1)
		elif ( ( table is not None ) or ( depth > 1 ) ) :
			self.add_output(table, table=table, context=context)

	def display_regex (self) :
		jsonTest = myPyJSON(splat=self.wants_splat(), cascade=self.wants_cascade())
		# Replace non-capturing (?: ... ) with widely supported, grep -E compliant ( ... )
		print(re.sub(r'[(][?][:]', '(', jsonTest.prolog), end="")
	
	def display_keyvalue (self) :
		self._default_mime = "application/json"
		table = {}
		if self.switches.get('key') is not None :
			table[self.switches.get('key')] = self.switches.get('value')
		self.display_data(table, table, parse=True, depth=0)
		if len(self.output) > 0 :
			print("\n".join(self.output), end=self.get_output_terminator())
		
	def execute (self) :
		try :
			
			try :
				lineInput = [ line for line in fileinput.input() ]
				jsonInput = myPyJSON(splat=self.wants_splat(), cascade=self.wants_cascade())
				jsonInput.accept( lineInput )
				jsonInput.select_where(self.selected)
				table = jsonInput.allData
			except json.decoder.JSONDecodeError as e :
				# This might be the full text of a report. Can we find the JSON PACKET:
				# envelope nestled within it and strip out the other stuff?
				jsonInput.accept( lineInput, screen=True ) 
				table = jsonInput.allData
			
			self.display_data(table, table, self.switches.get('parse'))
			if len(self.output) > 0 :
				print("\n".join(self.output), end=self.get_output_terminator())
				
		except json.decoder.JSONDecodeError as e :
	
			self.add_flag("json_error", jsonInput.raw)
		
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
	elif script.switched('regex') :
		script.display_regex()
	elif script.switched('version') :
		script.display_version()
	elif script.switched('key') and script.switched('value', just_present=True) :
		script.display_keyvalue()
	else :
		script.execute()
	sys.exit(script.get_exitcode())

		