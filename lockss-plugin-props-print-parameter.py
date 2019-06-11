#!/usr/bin/python3

import fileinput, re

for line in fileinput.input() :
	fields = line.rstrip().split("\t")
	param=fields[1]
	
	if (re.match('^PARAM[(]', fields[0])) :
		key=fields[2]
		value=fields[1]
	else :
		key=fields[0]
		value=fields[1]

	print(key.upper() + ":\t" + value)
