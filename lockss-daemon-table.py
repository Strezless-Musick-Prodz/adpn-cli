#!/usr/bin/python3
#
# lockss-daemon-table.py: Extract and report data from the LOCKSS daemon.
#
# @see LockssDaemonTable.__doc__ for usage notes
# @version 2021.0409

import sys, fileinput, re, json, csv, os.path
import urllib.request, urllib.parse, socket, html
from bs4 import BeautifulSoup
from getpass import getpass
from functools import reduce

from myLockssScripts import myPyCommandLine

class LockssDaemonTable :
    """
Usage: lockss-daemon-table.py [<XML>] [<OPTIONS>]... [--help]

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
        self._csv_reader = None
        
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
        
    @property
    def csv_reader (self) :
        return self._csv_reader
        
    @csv_reader.setter
    def csv_reader (self, reader) :
        self._csv_reader = reader
        
    def daemon_url (self) :

        url = None
        if ('daemon' in self.switches and not 'url' in self.switches) :
            if len(self.switches['daemon']) > 0 :
                daemonHost = urllib.parse.urlparse(self.switches['daemon'])
            else :
                daemonHost = urllib.parse.urlparse("http://localhost:8081")
                
            if ( daemonHost.netloc ) :
                daemonUrl = ( daemonHost.geturl() )
            else :
                daemonUrl = ( "http://%(daemon)s/" % self.switches )
            daemonPath = 'DaemonStatus?table=%(table)s&key=%(key)s&output=%(output)s'

            url = urllib.parse.urljoin(
                daemonUrl,
                (daemonPath % {'table': 'Plugins', 'key': '', 'output': 'xml'})
            )
        elif 'url' in self.switches :
            url = self.switches['url']
        
        return url

    def read_daemon_data (self) :
        if not (self.daemon_url() is None) :
            blob = self.get_from_url(self.daemon_url(), headers=True)
        elif len(sys.argv) > 1 :
            blob = { "body": ''.join(fileinput.input()), "head": [] }
        else :
            print("[%(script)s] Reading data from stdin" % {"script": script}, file=sys.stderr)
            blob = { "body": ''.join(fileinput.input()), "head": [] }

        return blob

    def get_username (self) :
        """Return a Username for scripted HTTP Authentication
        
        Returns the Username to be used in an HTTP Authentication handshake for the HTTP
        GET request sent by {@see LockssDaemonTable.get_from_url_with_authentication}
        This uses a value taken from the command line or default switches if available.
        If nothing is available from switches, it prints a prompt to stderr and reads the
        username from stdin.
        
        @return str a username for HTTP Authentication (e.g.: "User.Name")
        """
        return self.get_auth_parameter("user", "HTTP Username", input)

    def get_passwd (self) :
        """Return a Password for scripted HTTP Authentication

        Returns the Password to be used in an HTTP Authentication handshake for the HTTP
        GET request sent by {@see LockssDaemonTable.get_from_url_with_authentication}
        This uses a value taken from the command line or default switches if available.
        If nothing is available from switches, it prints a prompt to stderr and reads the
        password from stdin.

        @return str a password for HTTP Authentication (e.g.: "ChangeThisPassword")
        """
        return self.get_auth_parameter("pass", "HTTP Password", getpass)

    def get_realm (self) :
        """Return a Realm for scripted HTTP Authentication

        Returns the Realm to be used in an HTTP Authentication handshake for the HTTP
        GET request sent by {@see LockssDaemonTable.get_from_url_with_authentication}
        This uses a value taken from the command line or default switches if available.
        If nothing is available from switches, it prints a prompt to stderr and reads the
        password from stdin.

        @return str a realm for HTTP Authentication (e.g.: "LOCKSS Admin")
        """
        return self.get_auth_parameter("realm", "HTTP Authentication Realm", input)		

    def get_auth_parameter (self, key: str, title: str, inputFunction: "function") -> str :
        """Return a parameter for scripted HTTP Authentication
        
        Returns a parameter required for the HTTP Authentication handshake (e.g. username,
        password, or realm) on a scripted HTTP 	GET request sent by
        {@see LockssDaemonTable.get_from_url_with_authentication}. This uses a value
        taken from the command line or default switches if available. If nothing is
        available from switches, it redirects stdout to stderr, prints a prompt to the
        user console, and uses the provided console input function to read input from the
        user.

        @uses sys.stdout
        @uses sys.stderr
        
        @param str key the name of the switch to check for a value (e.g.: "user", "pass", "realm")
        @param str title The human-readable title. Used as a console input prompt if the
            value was not provided on command line or in default switches.
        @param function inputFunction The console input function used to read a value from
            the user console, if necessary.
            (E.g.: input for parameters that can be	displayed in cleartext,
            getpass for parameters that should not be.)
        @return str The parameter value retrieved from switches or from the user console.
        """
        if key in self.switches :
            param = self.switches[key]
        else :
            old_stdout = sys.stdout
            try :
                sys.stdout = sys.stderr
                param = inputFunction("%(title)s: " % {"title": title})
            finally :
                sys.stdout = old_stdout
        
        return param
        
    def get_from_url (self, url, headers=False) :
        """Retrieve data from a resource using HTTP GET

        Send an HTTP GET request to the resource located at a given URL, and return the body of the response
        If HTTP Authentication is required, fall back on self.get_from_url_with_authentication()
        If non-Authentication related HTTP errors are returned, raise an exception or display an error message
        
        @uses urllib.request.urlopen
        
        @param str url The URL to send a GET request to
        @return str the entire contents of the HTTP response body
        """

        try :
            if (self.switches['debug']) :
                print("[dbg] html=urllib.request.urlopen(url).read()", file=sys.stderr)
                print("[dbg] url=", url, file=sys.stderr)
            got=urllib.request.urlopen(url)
            html = got.read()
            if headers :
                html = { "head": got.getheaders(), "body": html }
        except urllib.error.HTTPError as e :
            if 401 == e.code :
                if (self.switches['debug']) :
                    print("[dbg] html = self.get_from_url_with_authentication(url)", file=sys.stderr)
                    print("[dbg] url=", url, file=sys.stderr)
                html = self.get_from_url_with_authentication(url, headers)
            else :
                raise

        return html
        
    def get_from_url_with_authentication (self, url, headers=False) :
        """Retrieve data from a resource using HTTP GET with HTTP Basic Authentication
        
        Send an HTTP GET request to the resource located at a given URL using HTTP Basic Authentication
        Return the body of the response. If the return is a network error or an HTTP
        client or server error code (400-599, etc.), then use LockssDaemonTable.do_handle_error
        to raise an exception or print out an error code.
        
        @param str url The URL to send a GET request to. Authentication credentials and realm are kept in user switches.
        @return str the entire contents of the HTTP response body
        """
        user = self.get_username()
        passwd = self.get_passwd()
        auth_realm = self.get_realm()
        
        auth_handler = urllib.request.HTTPBasicAuthHandler()
        auth_handler.add_password(realm=auth_realm, uri=url, user=user, passwd=passwd)
        opener = urllib.request.build_opener(auth_handler)
        
        urllib.request.install_opener(opener)

        try :
            got=urllib.request.urlopen(url)
            html = got.read()
            if headers :
                html = { "head": got.getheaders(), "body": html }
        except urllib.error.HTTPError as e :
            raise
            
        return html
        
    def get_soup (self, blob = None, headers = None) -> list :
        """Parse LOCKSS Daemon listing page into a two-dimensional table (list of lists)

        Parses CSV, XML or HTML contained in blob, presumably returned by the LOCKSS Daemon's
        query API, and returns a dictionary mapping the human-readable name of the Plugin
        to a row of Plugin Details including the URL of the JAR package, a unique ID code,
        etc. etc.

        @param str blob
        @return dict
        """
        
        if not ( blob is None ) :
            self.soup = BeautifulSoup(blob['body'], 'html.parser')
        
        if len(self.soup.find_all('st:table')) :
            data = self.get_xml_cells()
        else :
            raise ValueError('No XML table provided.')
        
        return data
    
    def get_xml_cell_value (self, xml_value) :
        value = []
        
        if xml_value is not None :
            # xml_value may contain: (1) a scalar value, represented by a string; OR
            # (2) an st:reference XML structure with name, key, and value elements
            if xml_value.find('st:reference') :
                for ref in xml_value.find_all('st:reference') :
                    if ref.find('st:name') :
                        value.append(ref.find('st:name').text)
                    if ref.find('st:key') :
                        value.append(ref.find('st:key').text)
                    if ref.find('st:value') : 
                        value.append(ref.find('st:value').text)
            else :
                value.append(xml_value.text)

        if len(value) == 0 :
            value = None
        elif len(value) == 1 :
            value = value[0]
        else :
            value = tuple(value)
        return value
        
    def get_xml_cells (self) :
        cols = { }
        data = { }
        
        url = self.daemon_url()
        
        for key in ['name', 'key', 'title'] :
            meta = self.soup.find('st:%(key)s' % { "key": key })
            if meta :
                data[key] = meta.text
        
        # Let's get column headers
        data["thead"] = {}
        for key in ['columndescriptor'] :
            metas = self.soup.find_all('st:%(key)s' % { "key": key })
            if metas :
                for meta in metas :
                    name = meta.find('st:name')
                    title = meta.find('st:title')
                    if name and title :
                        data["thead"][name.text] = title.text

        # Let's get table body by rows
        data["tbody"] = []
        for tr in self.soup.find_all('st:row') :
            named_row = {}
            anon_row = []
            for td in tr.find_all('st:cell') :
                # Does the cell have a column name?
                name = self.get_xml_cell_value(td.find('st:columnname'))
                value = self.get_xml_cell_value(td.find('st:value'))
                    
                if name :
                    named_row[name] = value
                else :
                    anon_row.append(value)
            
            if len(named_row.items()) > 0 : 
                data["tbody"].append(named_row)
            elif len(anon_row) > 0 :
                data["tbody"].append(anon_row)
        
        data["tfoot"] = []
        for summary in self.soup.find_all('st:summaryinfo') :
            xml_title = summary.find('st:title')
            xml_type = summary.find('st:type')
            xml_value = summary.find('st:value')
            summary = (self.get_xml_cell_value(xml_title), self.get_xml_cell_value(xml_type), self.get_xml_cell_value(xml_value))
            data["tfoot"].append(summary)
            
        return data
    
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
            if count > 1 :
                line="%(name)s\t%(url)s"
            else :
                line="%(url)s"
        elif self.switches['output']=='text/html' :
            esc = lambda text, place: html.escape(text)
            line='<li><a href="%(url)s">%(name)s</a></li>'
        
        return (line, esc)

    @property
    def delimiter (self) :
        return "\t"
        
    def display_row (self, row, cols=None) :
        
        if type(row) is dict :
            all_cols = ( cols if cols is not None else row.keys() )
            out_row = [ self.get_cell_text(row.get(col, None)) for col in all_cols ]
        else :
            out_row = [ self.get_cell_text(cell) for cell in row ]
        print(self.delimiter.join(out_row))

    def display (self, data: dict, show_head=True, done=True) :
        exitcode=1
        
        separated = False
        if self.switches.get('head') :
            for key in data.keys() :
                if not key in [ "thead", "tbody", "tfoot" ] :
                    print("%(key)s\t%(value)s" % { "key": key, "value": data[key] })
                    separated = True

        if not self.switches.get('no-body') :
            if 'thead' in data :
                cols = [ row for row in data['thead'] ]
                    
            if data.get('tbody') and len(data.get('tbody')) > 0 :
                if separated :
                    print("")
                    print("-- ")
                for row in data["tbody"] :
                    self.display_row(row, cols)
                    separated = True
                    exitcode=0
        
        if self.switches.get('foot') :
            if data.get('tfoot') :
                if separated :
                    print("")
                    print("-- ")
                for foot_row in data.get('tfoot') :
                    self.display_row(foot_row)
                    separated = True
                    exitcode=0

        if done :
            sys.exit(exitcode)

    def display_error (self, text, exitcode) :
        print("[%(script)s] %(message)s" % { "script": self.script, "message": text }, file=sys.stderr)
        if exitcode >= 0 :
            sys.exit(exitcode)
            
    def do_output_http_error (self, e: urllib.error.HTTPError) :
        mesg = "HTTP Error: %(code)d %(reason)s"
        if 401 == e.code :
            mesg = "Authentication error: %(reason)s"
        exitcode = (e.code - 200) % 256
        self.display_error(mesg % {"code": e.code, "reason": e.reason}, exitcode)

    def get_cell_text (self, cell) :
        result = None
        if cell is None :
            result = ""
        elif type(cell) is str :
            result = cell
        elif type(cell) is tuple or type(cell) is list :
            result = self.delimiter.join(cell)
        else :
            result = str(cell)
        return result
        
    def execute (self) :
        data = {}

        try :
            if (self.switches['debug']) :
                print("[dbg] blob=self.read_daemon_data()", file=sys.stderr)
            blob=self.read_daemon_data()
            if (self.switches['debug']) :
                print("[dbg] self.get_soup(blob)", file=sys.stderr)
            data = self.get_soup(blob)
        except FileNotFoundError as e :
            self.display_error(str(e), -1)
        except ValueError as e :
            self.display_error(str(e), -1)
        except urllib.error.HTTPError as e:
            self.do_output_http_error(e)
        except urllib.error.URLError as e:
            message = str(e.reason)
            exitcode = 255
            if isinstance(e.reason, socket.gaierror) :
                message = ("Socket Error %d: %s" % e.reason.args)
                exitcode = e.reason.args[0]
            self.display_error(message, exitcode)

        self.display(data, show_head=False, done=True)

if __name__ == '__main__':

    scriptname = sys.argv[0]
    scriptname = os.path.basename(scriptname)

    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
        "output": "text/tab-separated-values",
        "realm": "LOCKSS Admin",
        "url": None, "daemon": None,
        "debug": 0
    }).parse()

    if switches.get("url") is None :
        if switches.get("daemon") is None :
                if re.match(r'([A-Za-z][A-Za-z0-9\-]+)://', sys.argv[1]) :
                    switches["url"] = sys.argv[1]
                    switches["daemon"] = sys.argv[1]
        else :
            switches["url"] = switches["daemon"]
    switches["daemon"] = switches.get("url")
    
    script = LockssDaemonTable(scriptname, switches)
    if ('help' in switches) :
        script.display_usage()
    else :
        script.execute()
