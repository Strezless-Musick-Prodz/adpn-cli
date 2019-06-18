#!/usr/bin/python3
#
# lockss-plugin-props.py: Extract and report properties and configuration parameters
# contained in a LOCKSS Plugin XML file.
#
# Usage: lockss-plugin-props.py [<XMLFILE>] [--help] [--format=<MIME>] [--quiet] [--<KEY>=<VALUE> ...]
#
# Key plugin properties, each required parameter, and each plugin property dependent on
# those parameters will be printed out as one line of a table which can be represented in
# plain text, TSV, or HTML table format.
#
#	--help			display these usage notes
#	--format=<MIME>	supported values: text/plain, text/tab-separated-values, text/html
# 	--quiet			quiet mode, don't add section headers to text/plain or text/html output
#
# If no file name is provided, the script will read input from stdin
#
# Parameters can be filled in using switches of the format --<KEY>=<VALUE>
# For example:
#	--base_url=http://archives.alabama.gov/Lockss/ 	will set the parameter named 'base_url' to the value 'http://archives.alabama.gov/Lockss/'
#	--subdirectory=NARA_documents 					will set the parameter named 'subdirectory' to the value 'NARA_documents'
#
# @version 2019.0523

import sys, os.path, fileinput, re, cgi, json
from xml.dom import minidom

def getText(nodelist: list) -> str:
	"""A plain-text representation of all the text-node content contained in a list of DOM child nodes.

	Code derived from example code at {@link https://docs.python.org/2/library/xml.dom.minidom.html#dom-example}

	@param list nodelist An iterable list of DOM child node objects
	@return str The plain text contained (e.g., the child nodes of "<li>quick brown fox</li>" should return "quick brown fox")
	"""

	rc = []
	for node in nodelist:
		if node.nodeType == node.TEXT_NODE:
			rc.append(node.data)
	return ''.join(rc)

def getInputFromCommandLine() -> str:
	"""The text content of a file provided on the command line in the first command-line argument, or else piped into stdin.
	
	@return str The text content read in from the file, pipe or stdin.
	"""
	if (len(sys.argv) > 2) :
		lines = ''.join(fileinput.input(files=sys.argv[1:2]))
	else :
		lines = ''.join(fileinput.input())
	return lines

class LockssParameterDataTypes:
	def __init__ (self, code=-1, key="") :
		self.code=code
		self.key=key
		
	def CodeDictionary(self) -> dict:
		"""A hash map from data type names to numeric codes as defined for LOCKSS plugin XML documents.
		
		Type names to numeric codes defined as per {@link https://lockss.org/lockssdoc/gamma/daemon/constant-values.html#org.lockss.daemon.ConfigParamDescr.TYPE_BOOLEAN}
		
		@return dict
		"""
		return {
			'BOOLEAN': 5, 'INT': 2, 'LONG': 11, 'NUM_RANGE': 8, 'POS_INT': 6,
			'RANGE': 7, 'SET': 9, 'STRING': 1, 'TIME_INTERVAL': 12, 'URL': 3,
			'USER_PASSWD': 10, 'YEAR': 4
		}

	def Code(self) -> int:
		"""The numeric code for a data type as defined for LOCKSS plugin XML documents.
		
		Type names to numeric codes defined as per {@link https://lockss.org/lockssdoc/gamma/daemon/constant-values.html#org.lockss.daemon.ConfigParamDescr.TYPE_BOOLEAN}

		@uses LockssParameterDataTypes.CodeDictionary
		@uses LockssParameterDataTypes.code
		@uses LockssParameterDataTypes.key
		
		@return int A numeric code to be used in LOCKSS plugin XML documents (e.g. 2, 1, 3)
		"""
		if self.code > -1 :
			result = self.code
		else :
			result = self.CodeDictionary[self.key]
		
		return self.CodeDictionary[self.key]
	
	def TypeName(self) -> str:
		"""The human-readable name for a data type with a given numeric code as defined for LOCKSS plugin XML documents.
		
		Type names to numeric codes defined as per {@link https://lockss.org/lockssdoc/gamma/daemon/constant-values.html#org.lockss.daemon.ConfigParamDescr.TYPE_BOOLEAN}

		@uses LockssParameterDataTypes.CodeDictionary
		@uses LockssParameterDataTypes.code
		@uses LockssParameterDataTypes.key
		
		@param int key numeric code used in LOCKSS plugin XML documents (e.g. 2, 1, 3)
		@return int A human-readable name of the data type (e.g. "INT", "STRING", "URL")
		"""

		rc = []
		if len(self.key) > 0 :
			
			rc.append(self.key)

		else :

			codes = self.CodeDictionary()
			for type in codes.keys() :
				if self.code == codes[type] :
					rc.append(type)

		return ''.join(rc)
		
# /class LockssParameterDataTypes

class LockssPluginProps :

	def __init__ (self, xml: str) :
		"""Initialize the script and read in key-value pairs representing plugin properties from XML text input.
		
		@param str xml The XML content of a LOCKSS Plugin document.
		"""
		self.xmldoc = minidom.parseString(xml)

		pairs = self.xmldoc.getElementsByTagName('entry')

		collected_strings = {'plugin_identifier', 'plugin_name', 'plugin_version', 'au_start_url', 'au_manifest'}

		self.plugin_props = {}
		self.config_props = {}
		self.dependent_props = {}
		self.exitcode = 0
		
		for s in pairs:
			sKey = ''
			sValueType = ''
			vValue = None

			onKey = True
			for el in s.childNodes:
				if el.nodeType == el.ELEMENT_NODE:
					if onKey:
					
						if el.tagName == 'string' :
							onKey = False
							sKey = getText(el.childNodes)
							
					else :
					
						sValueType = el.tagName
						vValue = self.propertyValue(sValueType, el.childNodes)

			if sKey == 'plugin_config_props' :
				assert(sValueType == 'list')
				self.config_props = self.config_properties_from_nodes(vValue)
				
			elif sKey in collected_strings :
				assert(sValueType == 'string')
				self.plugin_props[sKey] = str(vValue)

			if isinstance(vValue, str) :
				if self.is_template(vValue) :
					self.dependent_props[sKey] = vValue

	def is_template (self, value: str) :
		return ('"' == value[0])
		
	def propertyValue (self, type: str, nodes: list) :
		"""The typed value of a plugin property, as encoded in LOCKSS Plugin XML
		
		The value may be a string literal, a numeric literal, a list of XML nodes, ...
		
		@param str type A data type, with the name taken from the tag name of the XML element (e.g. "string", "long", "list")
		@param list nodes
		@return mixed
		"""
		typeHandlers = {
			'string': lambda nodes: getText(nodes),
			'long': lambda nodes: int(getText(nodes)),
			'list': lambda nodes: nodes
		}
		
		if type in typeHandlers :
			vValue = typeHandlers[type](nodes)
		else :
			vValue = nodes
		return vValue
		
	def config_properties_from_nodes(self, list: list) -> dict:
		"""A hash map of plugin config parameter descriptions contained within an XML list, indexed by their key names
		
		@param list list An iterable list of DOM child node objects, expected to include
			`org.lockss.daemon.ConfigParamDescr` elements
		@return dict A map from parameter key names (e.g.: "base_url", "subdirectory", etc.)
			to a hash table of the parameter's key, data type, and human-readable description.
		"""
		PARAMETER_DESCRIPTION = 'org.lockss.daemon.ConfigParamDescr'

		props = {}
		for el in list :
			if el.nodeType == el.ELEMENT_NODE and el.tagName == PARAMETER_DESCRIPTION :
				param = { "key": None, "type": None, "displayName": None }

				for key in el.getElementsByTagName('key') :
					param['key'] = getText(key.childNodes)
				for displayName in el.getElementsByTagName('displayName') :
					param['displayName'] = getText(displayName.childNodes)
				for type in el.getElementsByTagName('type') :
					param['type'] = int(getText(type.childNodes))
					param['typeName'] = LockssParameterDataTypes(code=param['type']).TypeName()
					
				props[param['key']] = param
					
		return props

	def interpolate_properties(self, fmt: str, subs: dict) -> str :
		"""Format a LOCKSS property sprintf string by interpolating a set of config property values, if available.

		@param str fmt The sprintf format string
		@param dict subs The table of key-value pairs to interpolate into fmt, going from config property names to config property values
		@return str The formatted string, after any property values have been interpolated into it.
		"""
		if fmt[0] == '"' :
			quotesend = fmt.find('"', 1)
			fs = fmt[1:quotesend]
			fp = fmt[quotesend+1:].split(",")
			fp = [ _.strip() for _ in fp ]
			fp = list(filter(None, fp))
			ss = []
			for p in fp :
				assert(p in self.config_props);
				if p in subs :
					subbed = str(subs[p])
				else :
					subbed = "{" + p + "}"
					self.exitcode=2
				
				ss.append(subbed)
					
			fs = fs % tuple(ss)
		else :
			fs = fmt

		return fs

	def parameters (self) -> list :
		"""A list of property-value specifications, provided as Python command line arguments.
		
		@uses sys.argv
		@uses json.loads
		@uses json.JSONDecodeError
		@uses re.match
		
		@return list A list of zero or more hash tables, with each hash table mapping from property names to property values.
		"""
		if len(sys.argv) > 2 :
			jj = []
			hash = { }
			for j in sys.argv[2:] :
				try :
					jj.append(json.loads(j))
				except json.JSONDecodeError :
					refs = re.match( r'^--([A-Za-z_0-9.]+)(=(.*))?$', j )
					if refs :
						if refs.group(3) :
							hash[ refs.group(1) ] = refs.group(3)
						else :
							hash[ refs.group(1) ] = True
							
			if len(hash.keys()) :
				jj.append(hash)
				
		else :
			jj = [ { } ]

		return jj
		
	def display (self, subs: dict) :
		"""Output some basic data items for this plugin file to stdout.
		
		Each plugin property is printed out as one line of a table represented in TSV format

		@param dict subs A dictionary of named parameters to substitute into field values.
		"""
		displayed_items = {
			"plugin_identifier": "Plugin ID",
			"plugin_name": "Plugin Name",
			"plugin_version": "Plugin Version",
			"au_start_url":	"Start URL",
			"au_manifest": "Manifest URL"
		}
		
		# Set up output templates based on format (text/plain, text/tab-separated-values, text/html)
		txtReportHeader = ""
		txtPropertiesHeader = """
PLUGIN PROPERTIES:
------------------"""
		txtParamsHeader = """
PLUGIN PARAMETERS:
------------------"""
		txtDependentsHeader = """
CUSTOMIZED PROPERTIES:
----------------------"""

		txtPropertyLine = "%(description)s\t%(value)s"
		txtParameterLine = "%(type)s\t%(fieldvalue)s\t%(description)s"
		txtDependentLine = "%(description)s\t%(value)s\t%(raw)s"
		txtReportFooter = ""
		esc = lambda text: text

		if ('format' in subs) :
			if ('text/tab-separated-values' == subs['format']) :
				txtPropertiesHeader = ""
				txtParamsHeader = ""
				txtDependentsHeader = ""
				txtParameterLine = "PARAM(%(type)s):\t%(fieldvalue)s\t%(description)s"
			elif ('text/html' == subs['format']) :
				txtReportHeader = ("<!DOCTYPE html>\n<html lang='en'>\n<head>\n<title>LOCKSS Plugin: %(plugin_name)s</title>\n</head>\n<body>\n<table>\n<tbody>" % self.plugin_props)
				txtPropertiesHeader = "<tr><th colspan='3'>Properties</th></tr>"
				txtPropertyLine = "<tr id='property-%(field)s'><td class='property-name'>%(description)s:</td><td class='property-value' colspan='2'>%(value)s</td></tr>"
				txtParamsHeader = "<tr><th colspan='3'>Parameters</th></tr>"
				txtParameterLine = "<tr id='parameter-%(field)s'><td>PARAM(%(type)s):</td><td class='parameter-name'>%(fieldvalue)s</td><td class='parameter-description'>%(description)s</td></tr>"
				txtDependentsHeader = "<tr><th colspan='3'>Customized Properties</th></tr>"
				txtDependentLine = "<tr id='dependent-property-%(field)s'><td class='dependent-property-name'>%(description)s:</td><td class='dependent-property-value'>%(value)s</td><td class='dependent-property-template'>%(raw)s</td></tr>"
				txtReportFooter = "</tbody>\n</table>\n</body>\n</html>\n"
				esc = lambda text: cgi.escape(text, quote=True)

		print(txtReportHeader)
				
		# Print out all successfully collected XML elements with their values
		if len(txtPropertiesHeader) > 0 and not ('quiet' in subs) :
			print(txtPropertiesHeader)

		if 'jar' in subs :
			print(txtPropertyLine % {"field": "jar", "description": "Plugin JAR", "value": esc(subs['jar']), "raw": esc(subs['jar'])})
		
		for field in displayed_items.keys() :
			if field in self.plugin_props :
				fs = self.interpolate_properties(self.plugin_props[field], subs)
				print(txtPropertyLine % {"field": esc(field), "description": esc(displayed_items[field]), "value": esc(fs), "raw": esc(self.plugin_props[field])})

		# Print out the set of named configuration parameters with data type and description
		if len(self.config_props.keys()) > 0 :
			if len(txtParamsHeader) > 0 and not ('quiet' in subs) :
				print(txtParamsHeader)
			for propKey in self.config_props.keys():
				prop = self.config_props[propKey]
				field = propKey
				fieldvalue = propKey
				if (propKey in subs) :
					fieldvalue = field + "=" + json.dumps(subs[field])
				print(txtParameterLine % {"field": esc(field), "fieldvalue": esc(fieldvalue), "type": esc(prop['typeName']), 'description': esc(prop['displayName'])})
		
		# Print out the set of properties that are dependent on configuration parameters
		if len(txtDependentsHeader) > 0 and not ('quiet' in subs) :
			print(txtDependentsHeader)
		for field in self.dependent_props.keys() :
			fs = self.interpolate_properties(self.dependent_props[field], subs)
			print(txtDependentLine % {"field": esc(field), "description": esc(field), "value": esc(fs), "raw": esc(self.dependent_props[field])})
		
		if len(txtReportFooter) > 0 :
			print(txtReportFooter)
		
	def display_usage (self) :
		"""Output a command-line usage guide and then exit back to shell."""
		
		cmd = os.path.basename(sys.argv[0])
		print("Usage: " + cmd + """ [<XMLFILE>] [--help] [--format=<MIME>] [--quiet] [--<KEY>=<VALUE> ...]

Key plugin properties, each required parameter, and each plugin property dependent on
those parameters will be printed out as one line of a table which can be represented in
plain text, TSV, or HTML table format.

	--help              display these usage notes
	--format=<MIME>     supported values: text/plain, text/tab-separated-values, text/html
	--quiet             quiet mode, don't add section headers to text/plain or text/html output

If no file name is provided, the script will read input from stdin

Parameters can be filled in using switches of the format --<KEY>=<VALUE>
For example:

	--base_url=http://archives.alabama.gov/Lockss/

... will set the parameter named 'base_url' to the value 'http://archives.alabama.gov/Lockss/'
	
	--subdirectory=NARA_documents
	
... will set the parameter named 'subdirectory' to the value 'NARA_documents'	
""")
		sys.exit()
# /class LockssPluginProps

##########################################################################################
## MAIN SCRIPT BODY ######################################################################
##########################################################################################

if __name__ == '__main__' :
	xml = getInputFromCommandLine()

	lpp = LockssPluginProps(xml)
	for subs in lpp.parameters() :
		if 'help' in subs :
			lpp.display_usage()
			print()
		else :
			lpp.display(subs)

	# end for

	sys.exit(lpp.exitcode)
	
# That's all, folks.
