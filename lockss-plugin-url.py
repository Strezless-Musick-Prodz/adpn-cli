#!/usr/bin/python3
#
# lockss-plugin-url.py: Extract and report URL(s) for one or more LOCKSS Plugin JAR packages.
#
# @see LockssPluginDetails.__doc__ for usage notes
# @version 2019.0610

import sys, fileinput, re, json, os.path
import urllib.request, urllib.parse, html
from bs4 import BeautifulSoup
from getpass import getpass
from functools import reduce

from myLockssScripts import myPyCommandLine

class LockssPluginDetails :
	"""
Usage: lockss-plugin-url.py [<XML>] [--help]
	[--daemon=<HOST>|--url=<URL>] [--user=<NAME>] [--pass=<PASSWORD>]
	[--plugin=<NAME>|--plugin-regex=<PATTERN>|--plugin-keywords=<WORDS>|--plugin-id=<FQCN>]

Retrieves the URL for one given LOCKSS Publisher Plugin, based on the Plugin's
human-readable title, or a list of all of the avaliable LOCKSS Publisher Plugins, with
human-readable title and JAR URL. The result will be printed out to stdout. 

	--help                   	display these usage notes
	--daemon=<HOST>          	get info from LOCKSS Daemon at host <HOST>
	--url=<URL>              	get info from Publisher Plugins page located at <URL>
	--user=<NAME>           	use <NAME> for HTTP Auth when retrieving plugin details
	--password=<PASS>         	use <PASS> for HTTP Auth when retrieving plugin details
	--plugin=<NAME>         	display URL for the plugin whose human-readable name exactly matches <NAME>
	--plugin-regex=<PATTERN> 	display URL for the plugin name matching <PATTERN>
	--plugin-keywords=<WORDS> 	display URL for the plugin name containing keywords <WORDS>
	--plugin-id=<FQCN>       	display URL for the plugin whose ID is <FQCN>

If no Daemon URL is provided using --daemon or --url then the script will attempt to
read an XML or HTML Plugin listing from a local file. If no file name is provided, then
the script will try to read the HTML or XML listing from stdin.

If no HTTP username or password is provided on the command line, but the daemon requires
HTTP Authentication credentials, the script will prompt the user for the missing username
or password on stderr.
	"""

	def __init__ (self, script: str, switches: dict = {}) :
		self._switches = switches
		self._soup = None
		self._script = script

	@property
	def script (self) :
		return self._script

	@property
	def switches (self) :
		return self._switches

	@property
	def soup (self) :
		return self._soup
	
	@soup.setter
	def soup (self, soup) :
		self._soup = soup
		
	def daemon_url (self) :
	
		url = None
		if ('daemon' in self.switches and not 'url' in self.switches) :
			daemonUrl = 'http://%(daemon)s'
			daemonPath = '/DaemonStatus?table=%(table)s&key=%(key)s&output=(output)s'
			
			url = urllib.parse.urljoin(
				daemonUrl % {'daemon': self.switches['daemon']},
				(daemonPath % {'table': 'Plugins', 'key': '', 'output': 'xml'})
			)
		elif 'url' in self.switches :
			url = self.switches['url']
			
		return url

	def read_daemon_data (self) :
		if not (self.daemon_url() is None) :
			blob = self.get_from_url(self.daemon_url())
		elif len(sys.argv) > 1 :
			blob = ''.join(fileinput.input())
		else :
			print("[%(script)s] Reading Plugins XML/HTML list from stdin" % {"script": script}, file=sys.stderr)
			blob = ''.join(fileinput.input())
	
		return blob

	def get_username (self) :
		"""LockssPluginDetails.get_username(): get the Username to use when HTTP Authentication is required from switches or user console.

		If HTTP Authentication is required to retrieve a resource, get a username to send through the HTTP request.
		If the username is provided on the command line, use the command line switch.
		If the username is not provided on the command line, display a prompt to stderr and get input from stdin
		
		@uses sys.stdout
		@uses sys.stderr
		
		@return str a username for HTTP Authentication
		"""

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
		"""LockssPluginDetails.get_passwd(): get the Password to use when HTTP Authentication is required from switches or user console.

		If HTTP Authentication is required to retrieve a resource, get a password to send through the HTTP request.
		If the password is provided on the command line, use the command line switch.
		If the password is not provided on the command line, display a prompt to stderr and get input from stdin

		@return str a password for HTTP Authentication
		"""

		if 'pass' in self.switches :
			passwd = self.switches['pass']
		else :
			passwd = getpass(prompt="HTTP Password: ")
		return passwd

	def get_from_url (self, url) :
		"""LockssPluginDetails.get_from_url(): retrieve data from an resource using HTTP GET

		Send an HTTP GET request to the resource located at a given URL, and return the body of the response
		If HTTP Authentication is required, fall back on self.get_from_url_with_authentication()
		If non-Authentication related HTTP errors are returned, raise an exception or display an error message
		
		@param str url The URL to send a GET request to

		@return str the entire contents of the HTTP response body
		"""

		try :
			html = urllib.request.urlopen(url).read()
		except urllib.error.HTTPError as e :
			if 401 == e.code :
				html = self.get_from_url_with_authentication(url)
			else :
				self.do_handle_error(e)

		return html
		
	def get_from_url_with_authentication (self, url) :
		user = self.get_username()
		passwd = self.get_passwd()
			
		auth_handler = urllib.request.HTTPBasicAuthHandler()
		auth_handler.add_password(realm="LOCKSS Admin", uri=url, user=user, passwd=passwd)
		opener = urllib.request.build_opener(auth_handler)
		
		urllib.request.install_opener(opener)

		try :
			html = urllib.request.urlopen(url).read()
		except urllib.error.HTTPError as e :
			self.do_handle_error(e)

		return html

	def get_soup_jars (self, blob = None) :
		if not (blob is None) :
			self.soup = BeautifulSoup(blob, 'html.parser')
			
		if len(self.soup.find_all('html')) :
			pluginJars = self.get_html_scrape_jars()
		elif len(self.soup.find_all('st:table')) :
			pluginJars = self.get_xml_jars()
		else :
			raise ValueError('No XML/HTML available to scrape for Plugins.')
		
		return pluginJars
		
	def get_xml_jars (self) :
		cols = { }
		pluginJars = { }

		url = self.daemon_url()
		
		tablename = self.soup.find('st:name')
		if "Plugins" == tablename.text :
			col = 0
			for tr in self.soup.find_all('st:row') :
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
							subxml = self.get_from_url(linkedurl, { **self.switches, **{'error': 'raise'} }, '' )
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

	def get_html_scrape_jars (self) :
		forms = self.soup.find_all('form')

		url = self.daemon_url()
		
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

	def do_handle_error (self, e: Exception) :
	
		if ('error' in self.switches) and (self.switches['error'] == 'raise' ) :
			raise
		else :
			exitcode = (e.code - 200) % 256			
			self.do_output_http_error(e)
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
		
	def display (self, urls: list) :
	
		if len(urls)==1 :
			exitcode=0
		elif len(urls) > 1 :
			exitcode=2
		else :
			criteria = dict([ (key, self.switches[key]) for key in self.switches if re.match('plugin(-[A-Za-z0-9]+)?', key, re.I) ])
			
			print("[%(script)s] No Plugins found matching criteria: " % {"script": self.script}, criteria, file=sys.stderr)
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
	
	def do_output_http_error (self, e: urllib.error.HTTPError) :
		if 401 == e.code :
			mesg = "Authentication error: %(reason)s"
		else :
			mesg = "HTTP Error: %(code)d %(reason)s"
		print(("[%(script)s] " + mesg) % {"script": self.script, "code": e.code, "reason": e.reason}, file=sys.stderr)

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

	deets = LockssPluginDetails(script, switches)	
	if ('help' in switches) :
		deets.display_usage()

	pluginJars = {}
	try :
		blob=deets.read_daemon_data()
		pluginJars = deets.get_soup_jars(blob)
	except FileNotFoundError as e :
		print("[%(script)s] %(message)s" % { "script": script, "message": str(e) }, file=sys.stderr)
	except ValueError as e :
		print("[%(script)s] %(message)s" % { "script": script, "message": str(e) }, file=sys.stderr)
	
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
	
	deets.display(urls)
