#!/usr/bin/python3
#
# jar-manifest-property.py: Extract one or more properties from the key-value pairs
# contained in a jar file manifest
#
# Usage: jar-manifest-property.py [MANIFESTFILE]
#
# If no file name is provided, the script will read input from stdin
#
# @version 2019.0523

import sys, fileinput, re

map  = {}
header = ''

if len(sys.argv) > 1 :
	input = fileinput.input(files=sys.argv[1:2])
else :
	input = fileinput.input()

for line in input :
	line = line.strip();
	refs = re.match( r'^(\S+.*): (.*)$', line)
	if refs :
		header = refs.group(1)
		map[header] = refs.group(2)
	elif len(header) > 0 :
		map[header] = map[header] + line

if len(sys.argv) > 2 :
	for key in sys.argv[2:] :
		if (key in map) :
			print(map[key])
		else :
			print("!!!")
			
else :
	print(map)
