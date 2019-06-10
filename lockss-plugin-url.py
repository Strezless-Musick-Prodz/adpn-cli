#!/usr/bin/python3
#
# lockss-plugin-url.py: Extract and report URL(s) for one or more LOCKSS Plugin JAR package.
#
# Usage: lockss-plugin-url.py [<XMLFILE>] [--help] [--url=<URL>] [--user=<USERNAME>] [--pass=<PASSWORD>] [--plugin=<NAME>]
# [--format=<MIME>] [--quiet] [--<KEY>=<VALUE> ...]
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
# @version 2019.0607

import sys, fileinput, re, json
import urllib.request, urllib.parse
from bs4 import BeautifulSoup
from getpass import getpass

reSwitch = '--([0-9_A-z][^=]*)\s*=(.*)\s*$'

def KeyValuePair (switch) :
	ref=re.match(reSwitch, switch)
	return (ref[1], ref[2])

def LockssPropertySheet (html) :
	soup = BeautifulSoup(html, 'html.parser')
	forms = soup.find_all('form')

	cols = { }
	for form in forms :
		formtables = form.find_all('table')
		for table in formtables :
			trs = table.find_all('tr')
			for tr in trs :
				tds = tr.find_all('td')
				if len(tds) == 2 :
					keyvalue = [ td.text for td in tds ]
					key = ''.join([c for c in keyvalue[0] if c.isalpha()])
					value = keyvalue[1]
					cols[key] = value
	
	return cols

def do_output_http_error (e) :
	if 401 == e.code :
		print("Authentication error: " + e.reason, file=sys.stderr)
	else :
		print("HTTP Error: " + e.code + " " + e.reason, file=sys.stderr)					

def get_username (switches) :
	if 'user' in switches :
		user = switches['user'] 
	else :
		old_stdout = sys.stdout
		try :
			sys.stdout = sys.stderr
			user = input("HTTP Username: ")
		finally :
			sys.stdout = old_stdout
			
	return user

def get_passwd (switches) :
	if 'pass' in switches :
		passwd = switches['pass']
	else :
		passwd = getpass(prompt="HTTP Password: ")
	return passwd

def get_html_scrape_jars (soup) :
	forms = soup.find_all('form')

	cols = { }
	pluginJars = { }

	for form in forms :
		for tr in form.find_all('tr') :
			col = 0
			for td in tr.find_all('td') :
				elClass = ''
				if 'class' in td.attrs :
					elClass = ''.join(td.attrs['class'])
				
				if elClass == 'colhead' :
					cols[col] = td.text
				elif col in cols :
					th = cols[col]
					
					links = [ link for link in td.find_all('a') if ('Name' == th) ]

					# retrieve URL of JAR file
					for link in links :
					
						href = urllib.parse.urljoin(switches['url'], link.attrs['href'])
						
						try :
							subhtml = urllib.request.urlopen(href).read()
						except urllib.error.HTTPError :
							subhtml = ''
					
						props = LockssPropertySheet(subhtml)
						
						if 'URL' in props :
							pluginJars[td.text] = props['URL']
						
					# end for link
					
				col = col + 1
			# end for td
		# end for tr
	# end for form
	
	return pluginJars

def get_from_url (url, switches) :
	try :
		html = urllib.request.urlopen(switches['url']).read()
	except urllib.error.HTTPError as e :
		if 401 == e.code :
			html = get_from_url_with_authentication(switches['url'], switches)
		else :
			do_output_http_error(e)
			sys.exit(e.code)
	return html
	
def get_from_url_with_authentication (url, switches) :
	user = get_username(switches)
	passwd = get_passwd(switches)
		
	auth_handler = urllib.request.HTTPBasicAuthHandler()
	auth_handler.add_password(realm="LOCKSS Admin", uri=url, user=user, passwd=passwd)
	opener = urllib.request.build_opener(auth_handler)
	
	urllib.request.install_opener(opener)

	try :
		html = urllib.request.urlopen(url).read()
	except urllib.error.HTTPError as e :
		do_output_http_error(e)
		sys.exit(e.code)				
	return html
	
if __name__ == '__main__':

	switches = dict([ KeyValuePair(arg) for arg in sys.argv if re.match(reSwitch, arg) ])
	sys.argv = [ arg for arg in sys.argv if not re.match(reSwitch, arg) ]

	if (len(sys.argv) > 1) :
		html = ''.join(fileinput.input(files=sys.argv[1:2]))
	elif ('url' in switches) :
		html = get_from_url(switches['url'], switches)	
	else :
		html = ''.join(fileinput.input())
	
	soup = BeautifulSoup(html, 'html.parser')
	if len(soup.find_all('html')) :
		pluginJars = get_html_scrape_jars(soup)
	else :
		print("No HTML available to scrape.")
		sys.exit(1)

	for pluginName in pluginJars.keys() :

		if 'plugin' in switches :
			if re.match(switches['plugin'], pluginName) :
			
				print(pluginJars[pluginName])
				
		else :
		
			print(pluginName + "\t" + pluginJars[pluginName])
		
	sys.exit(0)
