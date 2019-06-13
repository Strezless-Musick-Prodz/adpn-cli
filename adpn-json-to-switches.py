#!/usr/bin/python3

import sys, os, fileinput
import re, json

if __name__ == '__main__' :

	script = sys.argv[0]
	script = os.path.basename(script)

	jsonInput = "".join(fileinput.input())
	
	table = json.loads(jsonInput)
	
	if ('Ingest Title' in table) :
		print('--au_title=%(name)s' % {"name": table['Ingest Title']})
	if ('Plugin JAR' in table) :
		print('--jar=%(url)s' % {"url": table['Plugin JAR']})
