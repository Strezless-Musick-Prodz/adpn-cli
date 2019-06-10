#!/usr/bin/python3
#
# lockss-plugin-url.py: Extract and report URL(s) for one or more LOCKSS Plugin JAR packages.
#
# Usage: lockss-plugin-url.py [<XMLFILE>] [--help] [--daemon=<HOST>|--url=<URL>] [--user=<USERNAME>] [--pass=<PASSWORD>] [--plugin=<NAME>|--plugin-regex=<PATTERN>]
#
# Retrieves the URL for one given LOCKSS Publisher Plugin, based on the Plugin's
# human-readable title, or a list of all of the avaliable LOCKSS Publisher Plugins, with
# human-readable title and JAR URL. The result will be printed out to stdout. 
#
#	--help					display these usage notes
# 	--daemon=<HOST>			get plugin information from the LOCKSS Daemon whose at host <HOST>
# 	--url=<URL>				get plugin information from Publisher Plugins page located at <URL>
# 	--user=<USERNAME>		use <USERNAME> for HTTP Authentication when retrieving plugin details
# 	--password=<PASSWORD> 	use <PASSWORD> for HTTP Authentication when retrieving plugin details
# 	--plugin=<NAME>			display the URL for the plugin whose human-readable name exactly matches <NAME>
# 	--plugin-regex=<PATTERN> display the URL for the plugin whose human-readable name matches <PATTERN>
#
# If no Daemon URL is provided using --daemon or --url then the script will attempt to
# read an XML or HTML Plugin listing from a local file. If no file name is provided, then
# the script will try to read the HTML or XML listing from stdin.
#
# If no HTTP username or password is provided on the command line, but the daemon requires
# HTTP Authentication credentials, the script will prompt the user for the missing username
# or password on stderr.
#
# @version 2019.0610

import sys, fileinput, re, json
import urllib.request, urllib.parse
from bs4 import BeautifulSoup
from getpass import getpass

reSwitch = '--([0-9_A-z][^=]*)\s*=(.*)\s*$'

def KeyValuePair (switch) :
	ref=re.match(reSwitch, switch)
	return (ref[1], ref[2])

def LockssPropertySheet (html) :
	stew = BeautifulSoup(html, 'html.parser')
	
	cols = { }
	if len(stew.find_all('html')) > 0 :
		forms = stew.find_all('form')

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

	elif len(stew.find_all('st:table')) > 0 :
		tableName = stew.find('st:name').text
		if ('PluginDetail' == tableName) :
			for td in stew.find_all('st:summaryinfo') :
				key = td.find('st:title').text
				value = td.find('st:value').text
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

def get_xml_jars (soup, switches) :
	cols = { }
	pluginJars = { }

	tablename = soup.find('st:name')
	if "Plugins" == tablename.text :
		col = 0
		for tr in soup.find_all('st:row') :
			for td in tr.find_all('st:cell') :
				th = td.find('st:columnname').text
				table = ''
				key = ''
				if 'plugin' == th :
					table = td.find('st:name').text
					key = td.find('st:key').text
					
					daemonurl = urllib.parse.urlsplit(switches['url'])
					
					iq = urllib.parse.parse_qs(daemonurl.query)
					oq = { }
					
					oq['table'] = [ table ]
					oq['key'] = [ key ]
					oq['output'] = iq['output']
					
					oquery = urllib.parse.urlencode(oq, doseq=True)
					
					# list elements: scheme, netloc, path, params, query, fragment
					linkedurl = urllib.parse.urlunparse([daemonurl.scheme, daemonurl.netloc, daemonurl.path, '', oquery, ''])

					# retrieve URL of JAR file
					try :
						subxml = get_from_url(linkedurl, { **switches, **{'error': 'raise'} } )
					except urllib.error.HTTPError :
						subxml = ''
				
					props = LockssPropertySheet(subxml)
					
					if 'URL' in props :
						Name = props['Name']
						pluginJars[Name] = props['URL']
					
				# end for link
			# end for td
		# end for tr
	# end for form
	
	return pluginJars

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
		html = urllib.request.urlopen(url).read()
	except urllib.error.HTTPError as e :
		if 401 == e.code :
			html = get_from_url_with_authentication(url, switches)
		elif ('error' in switches) and (switches['error'] == 'raise' ) :
			raise
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
		if ('error' in switches) and (switches['error'] == 'raise' ) :
			raise
		else :
			do_output_http_error(e)
			sys.exit(e.code)				

	return html
	
if __name__ == '__main__':

	switches = dict([ KeyValuePair(arg) for arg in sys.argv if re.match(reSwitch, arg) ])
	sys.argv = [ arg for arg in sys.argv if not re.match(reSwitch, arg) ]

	if 'daemon' in switches :
		if not 'url' in switches :
			switches['url'] = urllib.parse.urljoin('http://' + switches['daemon'], '/DaemonStatus?table=Plugins&output=xml')

	if (len(sys.argv) > 1) :
		html = ''.join(fileinput.input(files=sys.argv[1:2]))
	elif ('url' in switches) :
		html = get_from_url(switches['url'], switches)	
	else :
		html = ''.join(fileinput.input())
	
	soup = BeautifulSoup(html, 'html.parser')
	if len(soup.find_all('html')) :
		pluginJars = get_html_scrape_jars(soup)
	elif len(soup.find_all('st:table')) :
		pluginJars = get_xml_jars(soup, switches)	
	else :
		print("No XML/HTML available to scrape.", file=sys.stderr)
		sys.exit(1)
	
	exitcode=2
	urls = {}
	if 'plugin' in switches :
		urls = [ (pluginName, pluginJars[pluginName]) for pluginName in pluginJars.keys() if pluginName == switches['plugin'] ]
		
	elif 'plugin-regex' in switches :

		urls = [ (pluginName, pluginJars[pluginName]) for pluginName in pluginJars.keys() if re.match(switches['plugin-regex'], pluginName) ]
		
		
	else :
	
		urls = [ (pluginName, pluginJars[pluginName]) for pluginName in pluginJars.keys() ]
		
	if len(urls) > 2 :
		
		exitcode=2
		for pair in urls :
			print(pair[0] + "\t" + pair[1])

	elif len(urls) == 1 :
	
		exitcode=0
		print(urls[0][1])
		
	else :
		
		exitcode=1
		
	sys.exit(exitcode)
