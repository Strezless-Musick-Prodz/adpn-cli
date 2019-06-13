#!/usr/bin/python3

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
		