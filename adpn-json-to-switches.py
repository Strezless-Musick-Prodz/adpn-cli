#!/usr/bin/python3
#
# adpn-json-to-switches.py: utility script, converts data from a JSON hash table provided
# on stdin to switches used by adpn-ingest-test and related scripts.
#
# 	Usage: <INPUT> | adpn-json-to-switches.py -
#
# Input: a copy-pasted JSON hash table, possibly prefixed by a label like "JSON PACKET: "
# before the beginning of the {...} hash table structure. (The label will be ignored.)
#
# Output: a series of command-line switches, in --<KEY>=<VALUE> format. Written to stdout,
# one switch per line. For example:
#
# 	--au_title=WPA Folder 01
# 	--jar=http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar
# 	--plugin-id=gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin
# 	--remote=1
# 	--subdirectory=WPA-Folder-01
#
# @version 2019.0614

import sys, os, fileinput
import re, json

if __name__ == '__main__' :

	script = sys.argv[0]
	script = os.path.basename(script)

	exitcode = 0
	
	try :
		jsonInput = "".join(fileinput.input())
	
		ref=re.match("^([A-Za-z0-9]+\s*)+:\s*([{].*[}])\s*$", jsonInput)
		if (ref) :
			jsonInput = ref[2]
	
		table = json.loads(jsonInput)
	
		if ('Ingest Title' in table) :
			print('--au_title=%(name)s' % {"name": table['Ingest Title']})

		if ('Plugin JAR' in table) :
			print('--jar=%(url)s' % {"url": table['Plugin JAR']})
		if ('Plugin ID' in table) :
			print('--plugin-id=%(id)s' % {"id": table['Plugin ID']})
		elif ('Plugin Name' in table) :
			print('--plugin=%(name)s' % {"name": table['Plugin Name']})

		if ('File Size ' in table) :
			print('--remote=1')
				
		if ('parameters' in table) :
			if len(table) > 0 :
				for param, value in table['parameters'] :
					print('--%(KEY)s=%(VALUE)s' % {"KEY": param, "VALUE": value})
					
	except json.decoder.JSONDecodeError as e :
	
		print(
			("[%(script)s] JSON encoding error. Could not extract key-value pairs from "
			+ "the provided data:\n\n%(json)s")
			% {"script": script, "json": jsonInput},
			file=sys.stderr
		)
		exitcode = 1
		
	sys.exit(exitcode)
		