#!/usr/bin/python3
#
# adpn-ingest-into-titlesdb.py: accepts a JSON data packet provided by adpn-ingest-test
# and imports the data from it into ADPNet titlesdb MySQL database for a local test crawl
# or for publication to the LOCKSS network. 
#
# Prints out SQL code for injection of the title to stdout, in case you want to capture it
# for a (re)usable MySQL script.
#
# Exits with code 0 on success, or non-zero exit code on failure, to allow for pipelining
# with other ADPN Ingest tools.
#
# @version 2019.0624

import sys, os, fileinput, json, re
import MySQLdb

from myLockssScripts import myPyCommandLine
from myLockssScripts import myPyJSON

class ADPNIngestSQL :
	"""
Usage: ./adpn-ingest-into-titlesdb.py [OPTION]... [-|<JSONFILE>]

To get information:

  --help        	      	display these usage notes
  --list-peers            	list available peer node codes

To ingest AU metadata into titlesdb or publish to the network:

  --from=<PEER>           	mark the AU as provided by the node with code <PEER>
  --to=<PEER>|ALL         	publish this AU to the node with code <PEER> or to ALL nodes
  --dry-run               	print but do not issue the SQL queries for updating titlesdb
  
Required MySQL connection parameters:

  --mysql-host=<HOST>     	connect to MySQL host with name <HOST> (often 'localhost')
  --mysql-db=<DB>         	use the MySQL database named <DB>
  --mysql-user=<USER>    	connect using MySQL username <USER>
  --mysql-password=<PASS> 	connect using MySQL password <PASS>
  
JSON data for the AU to be ingested can be provided from a plain text file
or piped in to stdin.

MySQL parameters will probably be the same every time, so you may want to list them in the
adpn-ingest-into-titlesdb.defaults.conf plaintext file.

Returns exit code 0 on success.
1=A required parameter was omitted
2=There was a problem getting the key-value pairs from JSON input
	"""
	
	def __init__ (self, scriptname, switches, jsonText="") :
		self.scriptname = scriptname
		self._switches = switches
		self._jsonText = jsonText
		
		self._db = None
		self._cur = None
		
		self.accept_json(jsonText)
		
	@property
	def data (self) :
		return self._data
	
	@property
	def json (self) :
		return self._jsonText

	@property
	def switches (self) :
		return self._switches
	
	@property
	def db (self) :
		return self._db
	
	@db.setter
	def db (self, odb) :
		self._db=odb
	
	@property
	def cur (self) :
		return self._cur
		
	@cur.setter
	def cur (self, cur) :
		self._cur = cur

	def wants_json (self) -> bool :
		noJson = False
		for switch in ['help', 'list-peers'] :
			if switch in self.switches :
				noJson = (noJson or (len(self.switches[switch])>0))
		return (not noJson)

	def accept_json (self, jsonLines) :
		self._data = None
		
		jsonInput = myPyJSON()
		jsonInput.accept(jsonLines)

		try :
			jsonData = jsonInput.data
		except json.decoder.JSONDecodeError as e :
			jsonData = []
		
		self._data = {key: value for d in jsonData for key, value in d.items()}

	def wants_dry_run (self) -> bool :
		isDryRun = False
		if 'dry-run' in self.switches :
			isDryRun = (
				len(self.switches['dry-run']) > 0
				and self.switches['dry-run'] != 'n'
				and self.switches['dry-run'] != 'no'
			)
		return isDryRun
		
	def au_name (self, text: str) -> str :
		return re.sub(r"[^A-Za-z0-9]", "", text)
	
    def do_connect_to_db (self) :
 		self.db = MySQLdb.connect(
			host=self.switches['mysql-host'],
			user=self.switches['mysql-user'],
			passwd=self.switches['mysql-password'],
			db=self.switches['mysql-db']
		)
		self.cur = self.db.cursor()
   
	def do_insert_title (self, key_values: dict) :
		sql = """
INSERT INTO au_titlelist (au_id, au_pub_id, au_name, au_journal_title, au_type, au_title, au_plugin, au_approved_for_removal, au_content_size, au_disk_cost) VALUES (%(au_id)s, %(au_pub_id)s, %(au_name)s, %(au_journal_title)s, %(au_type)s, %(au_title)s, %(au_plugin)s, %(au_approved_for_removal)s, %(au_content_size)s, %(au_disk_cost)s);
		""" % key_values
		
		if not self.wants_dry_run() :
			self.cur.execute(sql)
		print(sql)

	def do_insert_param (self, key: str, value, i: int, key_values: dict) :
		au_titlelist_params_values = key_values
		au_titlelist_params_values['au_param'] = i
		au_titlelist_params_values['au_param_key'] = json.dumps(key)
		au_titlelist_params_values['au_param_value'] = json.dumps(value)
		au_titlelist_params_values['peer_au_limit'] = 'NULL'
		au_titlelist_params_values['is_definitional']  = json.dumps("y")
		
		sql = """
INSERT INTO au_titlelist_params (au_id, au_param, au_param_key, au_param_value, peer_au_limit, is_definitional) VALUES (%(au_id)s, %(au_param)s, %(au_param_key)s, %(au_param_value)s, %(peer_au_limit)s, %(is_definitional)s);
		""" % au_titlelist_params_values
		
		if not self.wants_dry_run() :
			self.cur.execute(sql)
		print(sql)

	def do_insert_peer_title (self, key_values: dict) :
		sql = """
INSERT INTO adpn_peer_titles (peer_id, au_id) VALUES (%(peer_id)s, %(au_id)s);
		""" % key_values
		
		try :
			if not self.wants_dry_run() :
				self.cur.execute(sql)
			print(sql)
		except MySQLdb._exceptions.IntegrityError as e :
			if e.args[0] == 1062 : # duplicate entry for key
				pass
			else :
				raise

	def initial_ingest (self, au_titlelist_values) :
		print("""
USE adpn;
		""")

		self.do_insert_title(au_titlelist_values)
		
		i=0
		for kv in self.data['parameters'] :
			key = kv[0]
			value = kv[1]
			i=i+1
			
			self.do_insert_param(key, value, i, au_titlelist_values)

	def publish_ingest (self, peer_id, au_titlelist_values) :
		adpn_peer_titles_values = au_titlelist_values
		adpn_peer_titles_values['peer_id'] = json.dumps(peer_id)
		self.do_insert_peer_title(adpn_peer_titles_values)
	
	def get_au_id(self) :
		au_name = json.dumps(self.au_name(self.data['Ingest Title']))
		self.cur.execute("SELECT au_id FROM au_titlelist WHERE au_name=%(au_name)s" % {"au_name": au_name})
		au_ids = [ row[0] for row in self.cur.fetchall() ]
		
		if len(au_ids) == 0 :
			self.switches['insert_title'] = True
			self.cur.execute("SELECT (MAX(au_id) + 1) AS au_id FROM au_titlelist")
			au_ids = [ row[0] for row in self.cur.fetchall() ]
			
		for id in au_ids :
			au_id = "%d" % (int(id))
		
		return au_id
	
	def get_peer(self, direction: str) -> str :
		switch = direction
		field = (direction + " peer").title()
		peer = ""
		if switch in self.switches :
			peer = self.switches[switch]
		elif field in self.data :
			peer = self.data[field]
		return peer
	
	def get_peers(self, active = "y") :
		criteria = []
		if len(active) > 0 :
			criteria=criteria+[ "active=%(active)s" % {"active": json.dumps(active)} ]
		
		whereClause = ""
		if len(criteria) > 0 :
			whereClause = "WHERE (" + (") AND (".join(criteria)) + ")"
			
		self.cur.execute("SELECT peer_id, host_name, daemon_version, config_server, peer_location, active, last_updated FROM `adpn_peers` %(whereClause)s" % {"whereClause": whereClause})

		return [ row for row in self.cur.fetchall() ]
		
	def display (self) :
        self.do_connect_to_db()
		
		self.switches['au_id'] = self.get_au_id()
		print("# au_id:", self.switches['au_id'])
			
		au_titlelist_values = {
		"au_id": int(self.switches['au_id']),
		"au_pub_id": self.get_peer('from'),
		"au_type": "journal",
		"au_title": self.data['Ingest Title'],
		"au_plugin": self.data['Plugin ID'],
		"au_approved_for_removal": "n",
		"au_content_size": 0,
		"au_disk_cost": 0,
		"peer_id": self.get_peer('to')
		}
		au_titlelist_values['au_journal_title'] = au_titlelist_values['au_title']
		au_titlelist_values['au_name'] = self.au_name(self.data['Ingest Title'])
		
		au_titlelist_values = [(key, au_titlelist_values[key]) for key in au_titlelist_values.keys()]
		au_titlelist_values = map(lambda kv: (kv[0], json.dumps(kv[1])), au_titlelist_values)
		au_titlelist_values = dict(au_titlelist_values)
		
		if self.switches['insert_title'] :
			self.initial_ingest(au_titlelist_values)
		self.publish_ingest(self.get_peer('to'), au_titlelist_values)
		
		self.db.commit()
		self.db.close()
	
	def display_peers (self) :
        self.do_connect_to_db()
		
		peers = self.get_peers()
		for peer in peers :
			line = (peer[0], 'ACTIVE' if (peer[5]=='y') else 'INACTIVE', str(peer[2]), peer[6].isoformat(' '))
			print("\t".join(line))
			
		self.db.close()

    def display_preserved_tables (self) :
        self.do_connect_to_db()
        
        # Initial ingests, peer assignments and promotions in titledb touch three (3) tables:
        #
        #   au_titlelist
        #   au_titlelist_params
        #   adpn_peer_titles
        #
        
        self.cur.execute("SELECT * FROM au_titlelist")
		au_titlelist = [ row[0] for row in self.cur.fetchall() ]

        for row in au_titlelist :
            print("\t".join(row))

        self.db.close()
 
	def display_usage (self) :
		print(self.__doc__)
		self.exit()
		
	def display_error (self, message) :
		print("[%(scr)s] %(msg)s" % {"scr": self.scriptname, "msg": message}, file=sys.stderr)
		
	def exit (self, exitcode: int = 0) :
		"""Terminate the current process with a given Unix-style exit code (0=OK, 1-255=error code)
		"""
		sys.exit(exitcode)
		
if __name__ == '__main__' :

	scriptname = sys.argv[0]
	scriptdir = os.path.dirname(scriptname)
	if len(scriptdir) > 0 :
		scriptdir = scriptdir + "/"
	scriptname = os.path.basename(scriptname)
	(slug, ext) = os.path.splitext(scriptname)
	defaultsFile = scriptdir + slug + ".defaults.conf"
	
	try :
		defaultArgv = sys.argv[0:0] + [ line.rstrip() for line in fileinput.input(files=defaultsFile) ]
	except IOError as e:
		defaultArgv = sys.argv[0:0] + []
	
	(defaultArgv, defaultSwitches) = myPyCommandLine(defaultArgv).parse()
	defaultSwitches = {**{"dry-run": "", "help": "", "list-peers": "", "insert_title": False}, **defaultSwitches}

	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults=defaultSwitches).parse()
	
	script = ADPNIngestSQL(scriptname, switches)
	try :
		script.accept_json(fileinput.input() if script.wants_json() else [])
	except KeyboardInterrupt as e :
		script.display_error("Data input aborted by user break.")
		
	exitcode = 0
	if len(switches['help']) > 0 :
		script.display_usage()
	elif len(switches['list-peers']) :
		script.display_peers()
    elif len(switches['snapshot']) :
        script.display_preserved_tables()
	elif script.data is None :
		exitcode = 2
		script.display_error("JSON encoding error. Could not extract key-value pairs from provided data.")
	else :
		try :
			script.display()
		except KeyError as e :
			exitcode = 1
			script.display_error("Parameter required: %(MissingKey)s" % {"MissingKey": e.args[0]})
			
	script.exit(exitcode)
