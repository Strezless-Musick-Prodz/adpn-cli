#!/usr/bin/python3
#
# lockss-plugin-url.py: Extract and report URL(s) for one or more LOCKSS Plugin JAR packages.
#
# Usage: lockss-plugin-url.py [<XML>]
# 	[--help]
# 	[--daemon=<HOST>|--url=<URL>] [--user=<NAME>] [--pass=<PASSWORD>]
# 	[--plugin=<NAME>|--plugin-regex=<PATTERN>|--plugin-keywords=<WORDS>|--plugin-id=<FQCN>]
#
# Retrieves the URL for one given LOCKSS Publisher Plugin, based on the Plugin's
# human-readable title, or a list of all of the avaliable LOCKSS Publisher Plugins, with
# human-readable title and JAR URL. The result will be printed out to stdout. 
#
#	--help					display these usage notes
# 	--daemon=<HOST>			get plugin info from LOCKSS Daemon at host <HOST>
# 	--url=<URL>				get plugin info from Publisher Plugins page located at <URL>
# 	--user=<NAME>			use <NAME> for HTTP Auth when retrieving plugin details
# 	--password=<PASSWORD> 	use <PASSWORD> for HTTP Auth when retrieving plugin details
# 	--plugin=<NAME>			display URL for the plugin whose human-readable name exactly matches <NAME>
# 	--plugin-regex=<PATTERN> 	display URL for the plugin name matching <PATTERN>
# 	--plugin-keywords=<WORDS> 	display URL for the plugin name containing keywords <WORDS>
# 	--plugin-id=<FQCN>		display URL for the plugin whose ID is <FQCN>
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

import sys, fileinput, re, json, os.path
import urllib.request, urllib.parse, html
from bs4 import BeautifulSoup
from getpass import getpass
from functools import reduce

from myLockssScripts import myPyCommandLine

class LockssPluginDetails :
	"""lockss-plugin-url.py: Extract and report URL(s) for one or more LOCKSS Plugin JAR packages.

	Usage: lockss-plugin-url.py [<XML>] [--help]
		[--daemon=<HOST>|--url=<URL>] [--user=<NAME>] [--pass=<PASSWORD>]
		[--plugin=<NAME>|--plugin-regex=<PATTERN>|--plugin-keywords=<WORDS>|--plugin-id=<FQCN>]

	Retrieves the URL for one given LOCKSS Publisher Plugin, based on the Plugin's
	human-readable title, or a list of all of the avaliable LOCKSS Publisher Plugins, with
	human-readable title and JAR URL. The result will be printed out to stdout. 

		--help					display these usage notes
		--daemon=<HOST>			get plugin info from LOCKSS Daemon at host <HOST>
		--url=<URL>				get plugin info from Publisher Plugins page located at <URL>
		--user=<NAME>			use <NAME> for HTTP Auth when retrieving plugin details
		--password=<PASSWORD> 	use <PASSWORD> for HTTP Auth when retrieving plugin details
		--plugin=<NAME>			display URL for the plugin whose human-readable name exactly matches <NAME>
		--plugin-regex=<PATTERN> 	display URL for the plugin name matching <PATTERN>
		--plugin-keywords=<WORDS> 	display URL for the plugin name containing keywords <WORDS>
		--plugin-id=<FQCN>		display URL for the plugin whose ID is <FQCN>

	If no Daemon URL is provided using --daemon or --url then the script will attempt to
	read an XML or HTML Plugin listing from a local file. If no file name is provided, then
	the script will try to read the HTML or XML listing from stdin.

	If no HTTP username or password is provided on the command line, but the daemon requires
	HTTP Authentication credentials, the script will prompt the user for the missing username
	or password on stderr.

	@version 2019.0610"""

	def __init__ (self, switches: dict = {}) :
		self._switches = switches
	
	@property
	def switches (self) :
		return self._switches

	def daemon_url (self) :
		daemonUrl = 'http://%(daemon)s'
		daemonPath = '/DaemonStatus?table=%(table)s&key=%(key)s&output=(output)s'
	
		if ('daemon' in self.switches and not 'url' in self.switches) :
			url = urllib.parse.urljoin(
				daemonUrl % {'daemon': self.switches['daemon']},
				(daemonPath % {'table': 'Plugins', 'key': '', 'output': 'xml'})
			)
		else :
			url = self.switches['url']
			
		return url

	def get_username (self) :
		if 'user' in self.switches :
			user = self.switches['user']
		else :
			old_stdout = sys.stdout
			try :
				sys.stdout = sys.stderr
				user = input("HTTP Username: ")
			finally :
				sys.stdout = old_stdout
				
		return user

	def get_passwd (self) :
		if 'pass' in self.switches :
			passwd = self.switches['pass']
		else :
			passwd = getpass(prompt="HTTP Password: ")
		return passwd

	def get_from_url (self, url, script) :
		try :
			html = urllib.request.urlopen(url).read()
		except urllib.error.HTTPError as e :
			if 401 == e.code :
				html = self.get_from_url_with_authentication(url, script)
			else :
				self.do_handle_error(e, script)

		return html
		
	def get_from_url_with_authentication (self, url, script) :
		user = self.get_username()
		passwd = self.get_passwd()
			
		auth_handler = urllib.request.HTTPBasicAuthHandler()
		auth_handler.add_password(realm="LOCKSS Admin", uri=url, user=user, passwd=passwd)
		opener = urllib.request.build_opener(auth_handler)
		
		urllib.request.install_opener(opener)

		try :
			html = urllib.request.urlopen(url).read()
		except urllib.error.HTTPError as e :
			self.do_handle_error(e, script)

		return html

	def do_handle_error (e: Exception, script: str) :
	
		if ('error' in self.switches) and (self.switches['error'] == 'raise' ) :
			raise
		else :
			exitcode = (e.code - 200) % 256			
			do_output_http_error(e, script)
			sys.exit(exitcode)

	def display_usage (self) :
		print(self.__doc__)
		sys.exit(0)

	def template_list (self, count: int) -> tuple:
		open = ""
		close = ""
		
		if self.switches['output']=='text/html' and count > 0 :
			open = "<ol>";
			close = "</ol>"
		
		return (open, close)
		
	def template (self, link: tuple, count: int) -> tuple:
		esc = lambda text, place: text
		if self.switches['output']=='text/tab-separated-values' :
			if len(urls)==1 :
				line="%(url)s"
			else :
				line="%(name)s\t%(url)s"
		elif self.switches['output']=='text/html' :
			esc = lambda text, place: html.escape(text)
			line='<li><a href="%(url)s">%(name)s</a></li>'
		
		return (line, esc)
		
	def display (self, urls: list, script: str) :
	
		if len(urls)==1 :
			exitcode=0
		elif len(urls) > 1 :
			exitcode=2
		else :
			criteria = dict([ (key, self.switches[key]) for key in self.switches if re.match('plugin(-[A-Za-z0-9]+)?', key, re.I) ])
			
			print("[%(script)s] No Plugins found matching criteria: " % {"script": script}, criteria, file=sys.stderr)
			line = ""
			exitcode=1
		
		(open, close) = self.template_list(len(urls))
		
		if len(open) > 0 :
			print(open)
			
		for pair in urls :
			(line, esc) = self.template(pair, len(urls))
			print(line % {"name": esc(pair[0], "name"), "url": esc(pair[1], "url")})
			
		if len(close) > 0 :
			print(close)
			
		sys.exit(exitcode)
	

def LockssPropertySheet (blob) :
	stew = BeautifulSoup(blob, 'html.parser')
	
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

def do_output_http_error (e, script) :
	if 401 == e.code :
		print("[" + script + "] Authentication error: " + e.reason, file=sys.stderr)
	else :
		print("[" + script + "] HTTP Error: " + str(e.code) + " " + e.reason, file=sys.stderr)					

def get_xml_jars (soup, url, deets) :
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
					
					daemonurl = urllib.parse.urlsplit(url)
					
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
						subxml = deets.get_from_url(linkedurl, { **deets.switches, **{'error': 'raise'} }, '' )
					except urllib.error.HTTPError :
						subxml = ''
				
					props = LockssPropertySheet(subxml)
					
					if 'URL' in props :
						Name = props['Name']
						pluginJars[Name] = props
					
				# end for link
			# end for td
		# end for tr
	# end for form
	
	return pluginJars

def get_html_scrape_jars (soup, url) :
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
					
						href = urllib.parse.urljoin(url, link.attrs['href'])
						
						try :
							subhtml = urllib.request.urlopen(href).read()
						except urllib.error.HTTPError :
							subhtml = ''
					
						props = LockssPropertySheet(subhtml)
						
						if 'URL' in props :
							pluginJars[td.text] = props
						
					# end for link
					
				col = col + 1
			# end for td
		# end for tr
	# end for form
	
	return pluginJars
	
def logical_product(sequence) :
	return reduce(lambda carry, found: (carry and (not not found)), sequence, True)

def keyword_match(keyword, text) :
	return re.search('\\b' + re.escape(keyword), text, re.I);

def make_keyword_match (text) :
	return lambda keyword: keyword_match(keyword, text)
	
if __name__ == '__main__':
	
	script = sys.argv[0]
	script = os.path.basename(script)

	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={"output": "text/tab-separated-values"}).parse()

	deets = LockssPluginDetails(switches)	
	if ('help' in switches) :
		deets.display_usage()
	
	if (len(sys.argv) > 1) :
		blob = ''.join(fileinput.input())
	elif not (deets.daemon_url() is None) :
		blob = deets.get_from_url(deets.daemon_url(), script)	
	else :
		print("[%(script)s] Reading Plugins XML/HTML list from stdin" % {"script": script}, file=sys.stderr)
		blob = ''.join(fileinput.input())
	
	soup = BeautifulSoup(blob, 'html.parser')
	if len(soup.find_all('html')) :
		pluginJars = get_html_scrape_jars(soup, deets.daemon_url())
	elif len(soup.find_all('st:table')) :
		pluginJars = get_xml_jars(soup, deets.daemon_url(), switches)	
	else :
		print("[%(script)s] No XML/HTML available to scrape." % {"script": script}, file=sys.stderr)
		pluginJars = {}
	
	plug_matchers = {
		'*': lambda name, row: True,
		'plugin': lambda name, row: (name.upper()==switches['plugin'].upper()),
		'plugin-regex': lambda name, row: re.search(switches['plugin-regex'], name, re.I),
		'plugin-keywords': lambda name, row: logical_product(map(make_keyword_match(name), switches['plugin-keywords'].split())),
		'plugin-id': lambda name, row: (row['Id']==switches['plugin-id']),
	}
	criteria = [ key for key in switches if re.match('plugin(-[A-Za-z0-9])?', key, re.I) ] + [ '*' ]
	
	plug_match = plug_matchers[criteria[0]]
	
	urls = [ (pluginName, pluginJars[pluginName]['URL'] ) for pluginName in pluginJars.keys() if plug_match(pluginName, pluginJars[pluginName]) ]
	
	deets.display(urls, script)
