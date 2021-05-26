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
# @version 2021.0526

import sys, os, fileinput, tempfile, datetime, json, csv, re
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
		self._records = None
		
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
	
	@property
	def records (self) :
		return self._records
	
	@records.setter
	def records (self, records) :
		self._records = records
	
	def wants_json (self) -> bool :
		noJson = False
		for switch in ['help', 'list-peers', 'snapshot'] :
			if switch in self.switches :
				noJson = (noJson or (len(self.switches[switch])>0))
		return (not noJson)

	def accept_json (self, jsonLines) :
		self._data = None
		
		jsonInput = myPyJSON(splat=True, cascade=True)
		jsonInput.accept(jsonLines)

		rescan=False
		try :
			jsonData = jsonInput.allData
		except json.decoder.JSONDecodeError as e :
			rescan=True

		if rescan :
			try :
				jsonInput.accept(jsonLines, screen=rescan)
				jsonData = jsonInput.allData
			except json.decoder.JSONDecodeError as e:
				jsonData = {}
		
		self._data = jsonData

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

	def do_insert_param (self, key: str, value, i: int, key_values: dict, op="INSERT", params_key_values={}) :
		au_param_key_values = {**{"peer_au_limit": None, "is_definitional": "y"}, **params_key_values}
		au_titlelist_params_values = key_values
		au_titlelist_params_values['au_param'] = i
		au_titlelist_params_values['au_param_key'] = json.dumps(key)
		au_titlelist_params_values['au_param_value'] = json.dumps(value)
		au_titlelist_params_values['peer_au_limit'] = json.dumps(au_param_key_values['peer_au_limit'] if ( au_param_key_values['peer_au_limit'] and au_param_key_values['peer_au_limit'] != "ALL") else None)
		au_titlelist_params_values['is_definitional']  = json.dumps(au_param_key_values['is_definitional'])
		
		if "DELETE" == op :
			sql = """
DELETE FROM au_titlelist_params WHERE au_id=%(au_id)s AND au_param=%(au_param)s;
			""" % au_titlelist_params_values
		elif "UPDATE" == op :
			sql = """
UPDATE au_titlelist_params SET au_param_key=%(au_param_key)s, au_param_value=%(au_param_value)s WHERE au_id=%(au_id)s AND au_param=%(au_param)s AND peer_au_limit=%(peer_au_limit)s;
			""" % au_titlelist_params_values
		else :
			sql = """
INSERT INTO au_titlelist_params (au_id, au_param, au_param_key, au_param_value, peer_au_limit, is_definitional) VALUES (%(au_id)s, %(au_param)s, %(au_param_key)s, %(au_param_value)s, %(peer_au_limit)s, %(is_definitional)s);
			""" % au_titlelist_params_values
		
		if not self.wants_dry_run() :
			self.cur.execute(sql)
		print(sql)

	def do_insert_peer_title (self, key_values: dict) :
		sql = ( "SELECT peer_id, au_id FROM adpn_peer_titles WHERE peer_id=%(peer_id)s AND au_id=%(au_id)s" % key_values )
		self.cur.execute(sql)
		peer_titles = [ row for row in self.cur.fetchall() ]
		
		if len(peer_titles) == 0 :
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
	
	def parameter_ingest (self, peer_id, op, pair, au_titlelist_values) :
		(i, sql_op) = self.get_au_param(pair, peer_id, op, au_titlelist_values )
		if not ( i is None ) and not ( sql_op is None ) :
			self.do_insert_param(key=pair[0], value=pair[1], i=i, op=sql_op, key_values=au_titlelist_values, params_key_values={"is_definitional": "n", "peer_au_limit": peer_id})
		
	def get_au_param(self, pair, peer_id, op, au_titlelist_values) :
		au_param_key = pair[0]
		hardcoded_ids = { "crawl_proxy": 98, "pub_down": 99 }
		
		au_param = None
		op_dne=( "INSERT" if op != "-" else None )
		op_ex=( "UPDATE" if op != "-" else "DELETE" )
		v_peer_id = ( peer_id if ( peer_id and peer_id != "ALL" ) else None )
		sql_match_peer = ( "peer_au_limit%(op)s%(peer_au_limit)s" % { "op": ( "=" if not v_peer_id is None else " IS " ), "peer_au_limit": json.dumps(v_peer_id) } )
		au_id = au_titlelist_values['au_id']
		sql = (
			"SELECT au_param, au_param_key, peer_au_limit, last_updated FROM au_titlelist_params WHERE au_id=%(au_id)s AND au_param_key=%(au_param_key)s AND %(match_peer)s ORDER BY au_param ASC"
			% {"au_id": json.dumps(au_id), "au_param_key": json.dumps(pair[0]), "match_peer": sql_match_peer }
		)
		self.cur.execute(sql)
		au_params = [ row[0] for row in self.cur.fetchall() ]
		op=(op_dne if len(au_params)==0 else op_ex)
		
		if au_param_key in hardcoded_ids :
			au_param = hardcoded_ids[au_param_key]
			au_params = [ au_param ]
		
		elif len(au_params) == 0 :
			self.cur.execute(
				"SELECT au_param, au_param_key, peer_au_limit, last_updated FROM au_titlelist_params WHERE au_id=%(au_id)s ORDER BY au_param ASC"
				% {"au_id": json.dumps(au_id) }
			)
			au_params = [ row[0] for row in self.cur.fetchall() ]
			
			if len(au_params) == 0 :
				au_param = 1
			else :
				candidates = [ x for x in range(min(au_params), max(au_params) + 2) if not x in au_params ]
				# max + 1 on the stop parameter includes max; max + 2 includes the first int after max
				au_param = candidates[0] # first available
				
		else :
			au_param = au_params[0]
			
		return ( au_param, op )
	
	def get_au_id(self) :
		# Is au_id explicitly provided on the command line?
		au_ids = [ ]
		if 'au_id' in self.switches :
			au_ids = [ self.switches['au_id'] ]
		
		# FALL BACK: can we get the au_id from a unique au_name?
		if len(au_ids) == 0 and 'AU Name' in self.data :
			au_name = json.dumps(self.data['AU Name'])
			self.cur.execute("SELECT au_id FROM au_titlelist WHERE au_name=%(au_name)s" % {"au_name": au_name})
			au_ids = [ row[0] for row in self.cur.fetchall() ]
		
		# FALL BACK: can we get the au_id by filtering Ingest Title into a unique au_name?
		if len(au_ids) == 0 and 'Ingest Title' in self.data :
			au_name = json.dumps(self.au_name(self.data['Ingest Title']))
			self.cur.execute("SELECT au_id FROM au_titlelist WHERE au_name=%(au_name)s" % {"au_name": au_name})
			au_ids = [ row[0] for row in self.cur.fetchall() ]
		
		# We do not have an au_id candidate. Let's mint a new au_id number and get ready to insert into au_titlelist
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
	
	def get_mysql_table_state(self, table: str) :	
		self.cur.execute("SHOW COLUMNS FROM " + table)
		cols = [ column[0] for column in self.cur.fetchall() ]
		self.cur.execute("SELECT * FROM " + table)
		rows = [ row for row in self.cur.fetchall() ]
		return { "cols": cols, "rows": rows }
		
	def get_au_titlelist_table_state(self) :
		return self.get_mysql_table_state("au_titlelist")

	def get_au_titlelist_params_table_state(self) :
		return self.get_mysql_table_state("au_titlelist_params")

	def get_adpn_peer_titles_table_state(self) :
		return self.get_mysql_table_state("adpn_peer_titles")
	
	def get_peers(self, active = "y") :
		criteria = []
		if len(active) > 0 :
			criteria=criteria+[ "active=%(active)s" % {"active": json.dumps(active)} ]
		
		whereClause = ""
		if len(criteria) > 0 :
			whereClause = "WHERE (" + (") AND (".join(criteria)) + ")"
			
		self.cur.execute("SELECT peer_id, host_name, daemon_version, config_server, peer_location, active, last_updated FROM `adpn_peers` %(whereClause)s" % {"whereClause": whereClause})

		return [ row for row in self.cur.fetchall() ]
		
	def get_data_from_db (self, field, multiple=False) :
		rex = None
		if self.records is None :
			sql = ( "SELECT * FROM au_titlelist WHERE au_id=%(au_id)s" % { "au_id": json.dumps(self.switches['au_id']) } )
			self.cur.execute(sql)
			records = [ record for record in self.cur.fetchall() ]
			columns = [ column[0] for column in self.cur.description ]
			self.records = [ [ ( columns[idx], data ) for idx, data in enumerate(record) ] for record in records ]
		
		rex = [ [ col[1] for col in record if col[0]==field ][0] for record in self.records ]
		if not multiple :
			rex = ( rex[0] if len(rex) > 0 else None )
		
		return rex
	
	def get_ingest_title (self) :
		title = None
		if 'Ingest Title' in self.data :
			title = self.data['Ingest Title']
		elif self.switches['au_id'] :
			title = self.get_data_from_db('au_title')
		return title
		
	def get_plugin_id (self) :
		plugin = None
		if 'Plugin ID' in self.data :
			plugin = self.data['Plugin ID']
		elif self.switches['au_id'] :
			plugin = self.get_data_from_db('au_plugin')
		return plugin
	
	def display (self) :
		self.do_connect_to_db()
		
		self.switches['au_id'] = self.get_au_id()
		print("# au_id:", self.switches['au_id'])
		
		peer_to = self.get_peer('to')
		peer_to = ( peer_to if peer_to else 'ALL' )
		
		au_titlelist_values = {
		"au_id": int(self.switches['au_id']),
		"au_pub_id": self.get_peer('from'),
		"au_type": "journal",
		"au_title": self.get_ingest_title(),
		"au_plugin": self.get_plugin_id(),
		"au_approved_for_removal": "n",
		"au_content_size": 0,
		"au_disk_cost": 0,
		"peer_id": peer_to
		}
		au_titlelist_values['au_journal_title'] = au_titlelist_values['au_title']
		au_titlelist_values['au_name'] = self.au_name(au_titlelist_values['au_title'] if au_titlelist_values['au_title'] else "")
		raw_au_titlelist_values = au_titlelist_values
        
		au_titlelist_values = [(key, au_titlelist_values[key]) for key in au_titlelist_values.keys()]
		au_titlelist_values = map(lambda kv: (kv[0], json.dumps(kv[1])), au_titlelist_values)
		au_titlelist_values = dict(au_titlelist_values)
		
		if 'au' == self.switches['test'] :
			print(au_titlelist_values)
		elif raw_au_titlelist_values["au_title"] is None :
			script.display_error("Parameter Required: Ingest Title")
		elif raw_au_titlelist_values["au_plugin"] is None :
			script.display_error("Parameter Required: Plugin ID")
		else :
			if self.switches['insert_title'] :
				self.initial_ingest(au_titlelist_values)
			if self.switches['insert_peer_title'] :
				self.publish_ingest(peer_to, au_titlelist_values)
			
			if 'parameter' in self.switches :
				param_parts = re.match(string=self.switches['parameter'], pattern='^([+\-]?)(.*)$')
				param_op = ( param_parts[1] if param_parts[1] else "+" )
				param_pair = param_parts[2]
				param_pair = ( re.split(string=param_pair, pattern="[:]", maxsplit=1) + [ "" ] )[0:2]
				self.parameter_ingest(peer_to, param_op, param_pair, au_titlelist_values)
			
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
		
		outpath = self.switches['output']
		sdate = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

		tables = {
			"au_titlelist": self.get_au_titlelist_table_state,
			"au_titlelist_params": self.get_au_titlelist_params_table_state,
			"adpn_peer_titles": self.get_adpn_peer_titles_table_state
		}
		
		for k, m in tables.items() :
			out_filename=( outpath + "/snapshot-" + self.switches['mysql-db'] + "-" + k + "-" + sdate + ".csv" )
			print("* Writing table [" + k + "] rows to " + out_filename, end=" ... ")
			try :
				with open(out_filename, 'w') as f :
					out_csv = csv.writer(f)
					state = m()
					print("#", end="", file=f)
					out_csv.writerow(state["cols"])
					for row in state["rows"] :
						out_csv.writerow(row)
					print( "(ok)" )
			except IOError as e :
				print( "[ERROR!]" )
			
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
	defaultSwitches = {**{
		"dry-run": "",
		"help": "",
		"list-peers": "",
		"snapshot": "",
		"output": tempfile.gettempdir(),
		"insert_title": False,
		"insert_peer_title": True,
		"test": ""
	}, **defaultSwitches}

	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults=defaultSwitches).parse()
	
	script = ADPNIngestSQL(scriptname, switches)
	try :
		lineinput = [ line for line in fileinput.input() ] if script.wants_json() else []
		script.accept_json(lineinput)
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
