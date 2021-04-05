`adpn` provides a set of command-line tools for the ADPNet LOCKSS digital
preservation network.

There are tools to manage the entire process of preparing, staging, accepting,
and publishing an Archival Unit (AU) for distributed preservation in the
network:

* `adpn preserve` allows an ADPNet network member to package digital data files
  for submission to the network as an Archival Unit (AU).
  
* `adpn verify` allows the manager of an ADPNet preservation node to verify that
  a submitted AU is accessible from their preservation node.
  
* `adpn ingest` allows the manager of the ADPNet network props server to accept
  a verified AU and prepare a test node for test crawls of the resource.
  
* `adpn publish` allows the manager of the ADPNet network props server to mark
  an ingested AU as available to the entire preservation network.

There are also tools to manage some labor-intensive systems administration
tasks when managing a LOCKSS preservation node on ADPNet:

* `adpn rebalance` provides a set of tools for safely rebalancing AUs stored on
  different volumes of a LOCKSS box's cache. For example: if the /cache0 volume
  gets too full, this helps move AUs stored on /cache0 to /cache1 or /cache2

* `adpn plugins` provides tools for reviewing and managing properties of LOCKSS
  plugins used by ADPNet nodes.

There are also tools to manage some common database and management tasks when
administering the ADPNet props server titlesdb database:

* `adpn publisher` provides a set of tools for listing or adding publishers who
  may submit AUs for preservation in LOCKSS.

Development started in May 2019 by Charles Johnson, Collections Archivist,
Alabama Department of Archives and History (<charlesw.johnson@archives.alabama.gov>).

All the original code in here is hereby released into the public domain. Any code copied
or derived from other public sources is noted in comments, and is governed by the
licensing terms preferred by the authors of the original code. (CJ, 2019/05/23)

Requirements and Dependencies
=============================
To use the adpn suite of utility scripts, you need:

* A [GNU bash][] command-line and scripting environment. This usually means running either:
  (1) [GNU/Linux][], (2) the [Cygwin][] command-line environment on Windows, or (3) the
  [Terminal.app][] terminal emulator on Macs with OS X.

* [Python 3][] scripting language

### GNU command-line tools: ###
  * [unzip](https://linux.die.net/man/1/unzip): `sudo apt install unzip`
  * [curl]: `sudo apt install curl`
  
### Python 3 utilities and library modules: ###

  * [pip][] (Python package installer): `sudo apt install python3-pip`
  * [python3-bs4][] (BeautifulSoup): `sudo apt install python3-bs4`
  * [python3-socks][] (socks): `sudo apt install python3-socks`
  * [mysqlclient][] (Python 3 MySQLdb): `sudo pip install mysqlclient`
  
[GNU bash]: https://www.gnu.org/software/bash/
[GNU/Linux]: https://en.wikipedia.org/wiki/Linux
[Cygwin]: https://cygwin.com/
[Terminal.app]: https://en.wikipedia.org/wiki/Terminal_(macOS)
[Python 3]: https://www.python.org/
[unzip]: https://linux.die.net/man/1/unzip
[curl]: https://linux.die.net/man/1/curl
[pip]: https://pypi.org/project/pip/
[python3-bs4]: https://pypi.org/project/beautifulsoup4/
[python3-socks]: https://pypi.org/project/PySocks/
[mysqlclient]: https://pypi.org/project/mysqlclient/

adpn CLI Tools
=============

adpn preserve
-------------
Packages digital data files into a LOCKSS archival format, transmits them to an
accessible staging location, and provides structured data for the ingest manager
to accept and verify the AU for ingest.

Usage:

	(Under construction!)
	
adpn verify
-----------
Verify that the start URL for an AU submitted by a publisher is valid and can be
successfully crawled from the current preservation node. Also prepares data to
be piped in to `adpn ingest` or `adpn publish` on the ADPNet props server.

Usage:

	adpn verify gitlab:<ISSUEREFERENCE>
	adpn verify [<FILE>]
	cat <FILE> | adpn verify -

For example:

	adpn verify 'gitlab:adpnet/adpn---general#77'
	
Verifies the AU referenced in Gitlab repository adpnet/adpn---general, issue #77.

Sample output (to be pasted into the Gitlab Issue, or otherwise sent back to the ingest manager):

~~~
[charlesw.johnson@adpnadah adpn-cli]$ adpn --version
adpn version 2021.0402
[charlesw.johnson@adpnadah adpn-cli]$ adpn verify 'gitlab:adpnet/adpn---general#77'

INGEST INFORMATION AND PARAMETERS:
----------------------------------
INGEST TITLE:   Alabama Department of Archives and History: Q-Numbers Masters: Q0000106501-Q0000107000m
FILE SIZE:      49.91 GiB (53,590,679,164 bytes, 515 files)
PLUGIN JAR:     http://configuration.adpn.org/overhead/takeover/plugins/AuburnDirectoryPlugin.jar
PLUGIN ID:      edu.auburn.adpn.directory.AuburnDirectoryPlugin
PLUGIN NAME:    Auburn Directory Plugin
PLUGIN VERSION: 6
INGEST REPORT:  http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m.au.txt
INGEST STEP:    verified
BASE URL:       base_url="http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/"
DIRECTORY NAME: directory="Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m"

JSON PACKET:    {"Ingest Title": "Alabama Department of Archives and History: Q-Numbers Masters: Q0000106501-Q0000107000m", "File Size": "49.91 GiB (53,590,679,164 bytes, 515 files)", "From Peer": "ADAH", "To Peer": "ADAH", "Ingest Report": "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m.au.txt", "Ingest Step": "verified", "Plugin JAR": "http://configuration.adpn.org/overhead/takeover/plugins/AuburnDirectoryPlugin.jar", "Plugin ID": "edu.auburn.adpn.directory.AuburnDirectoryPlugin", "Plugin Name": "Auburn Directory Plugin", "Plugin Version": "6", "Start URL": "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m/manifest.html", "Base URL": "base_url=\"http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/\"", "Directory name": "directory=\"Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m\"", "au_name": "Auburn Directory Plugin, Base URL http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/, Directory Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m", "au_start_url": "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m/manifest.html", "parameters": [["base_url", "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/"], ["directory", "Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m"]]}

URL RETRIEVAL TESTS:
--------------------
200     OK      au_start_url    http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m/manifest.html     "%s%s/manifest.html", base_url, directory
~~~
	
adpn ingest
-----------
Accept an AU that has been verified by a node manager and add the AU to that node's live
feed of AUs for ingest and preservation (titlesdb). This step sets up the 1st and 2nd
test crawls of an AU that has been staged for ingest.

Usage:

	adpn ingest gitlab:<ISSUEREFERENCE> [--to=<PEER>] [--dry-run]
	adpn ingest [<FILE>] [--to=<PEER>] [--dry-run]
	cat <FILE> | adpn verify - [--to=<PEER>] [--dry-run]

Options:
--to=<PEER>		make AU visible to this peer (AUB, ADAH, ...; ALL=whole network)
--dry-run   	display SQL script to insert AU into titlesdb but do not execute

For example:

	adpn ingest 'gitlab:adpnet/adpn---general#77'
	
Sample output (to be pasted back into the Gitlab issue, or otherwise sent back to the ingest manager):

~~~
INGEST INFORMATION AND PARAMETERS:
----------------------------------
INGEST TITLE:   Alabama Department of Archives and History: Q-Numbers Masters: Q0000106501-Q0000107000m
FILE SIZE:      49.91 GiB (53,590,679,164 bytes, 515 files)
PLUGIN JAR:     http://configuration.adpn.org/overhead/takeover/plugins/AuburnDirectoryPlugin.jar
PLUGIN ID:      edu.auburn.adpn.directory.AuburnDirectoryPlugin
PLUGIN NAME:    Auburn Directory Plugin
PLUGIN VERSION: 6
INGEST REPORT:  http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m.au.txt
INGEST STEP:    ingested
BASE URL:       base_url="http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/"
DIRECTORY NAME: directory="Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m"

JSON PACKET:    {"Ingest Title": "Alabama Department of Archives and History: Q-Numbers Masters: Q0000106501-Q0000107000m", "File Size": "49.91 GiB (53,590,679,164 bytes, 515 files)", "From Peer": "ADAH", "To Peer": "ADAH", "Ingest Report": "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m.au.txt", "Ingest Step": "ingested", "Plugin JAR": "http://configuration.adpn.org/overhead/takeover/plugins/AuburnDirectoryPlugin.jar", "Plugin ID": "edu.auburn.adpn.directory.AuburnDirectoryPlugin", "Plugin Name": "Auburn Directory Plugin", "Plugin Version": "6", "Start URL": "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m/manifest.html", "Base URL": "base_url=\"http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/\"", "Directory name": "directory=\"Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m\"", "au_name": "Auburn Directory Plugin, Base URL http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/, Directory Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m", "au_start_url": "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m/manifest.html", "parameters": [["base_url", "http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/"], ["directory", "Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m"]]}

URL RETRIEVAL TESTS:
--------------------
200     OK      au_start_url    http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m/manifest.html     "%s%s/manifest.html", base_url, directory


* Writing table [au_titlelist] rows to /tmp/snapshot-adpn-au_titlelist-20210402135826.csv ... (ok)
* Writing table [au_titlelist_params] rows to /tmp/snapshot-adpn-au_titlelist_params-20210402135826.csv ... (ok)
* Writing table [adpn_peer_titles] rows to /tmp/snapshot-adpn-adpn_peer_titles-20210402135826.csv ... (ok)
--- /home/cjohnson/titlesdb-xml/titlesdb.ADAH-0.0.xml   2021-04-02 13:58:26.229566201 -0500
+++ /home/cjohnson/titlesdb-xml/titlesdb.ADAH-0.1.xml   2021-04-02 13:58:27.545559109 -0500
@@ -5386,6 +5386,30 @@
             </property></property></property>
 <property name="org.lockss.titleSet">

+  <property name="Alabama Department of Archives and History">
+   <property name="name" value="All Alabama Department of Archives and History AUs" />
+   <property name="class" value="xpath" />
+   <property name="xpath" value="[attributes/publisher='Alabama Department of Archives and History']" />
+  </property>
+
+ </property> <property name="org.lockss.title">
+   <property name="AlabamaDepartmentofArchivesandHistoryQNumbersMastersQ0000106501Q0000107000m">
+    <property name="attributes.publisher" value="Alabama Department of Archives and History" />
+    <property name="journalTitle" value="Alabama Department of Archives and History: Q-Numbers Masters: Q0000106501-Q0000107000m" />
+    <property name="type" value="journal" />
+    <property name="title" value="Alabama Department of Archives and History: Q-Numbers Masters: Q0000106501-Q0000107000m" />
+    <property name="plugin" value="edu.auburn.adpn.directory.AuburnDirectoryPlugin" />
+
+            <property name="param.1">
+                <property name="key" value="base_url" />
+                <property name="value" value="http://drop.adpn.org/drop-server/adah/drop_au_content_in_here/" />
+            </property>
+            <property name="param.2">
+                <property name="key" value="directory" />
+                <property name="value" value="Digitization-Masters-Q-numbers-Master-Q0000106501_Q0000107000m" />
+            </property></property></property>
+<property name="org.lockss.titleSet">
+
   <property name="Alabama Digital Preservation Network">
    <property name="name" value="All Alabama Digital Preservation Network AUs" />
    <property name="class" value="xpath" />

[adpn ingest] DONE: Archival Unit ingested into ADAH titlesdb.
cjohnson@lockss-adpn-con:/home/cjohnson/bin/adpn-cli$
~~~

adpn publish
------------
Given an AU that has been submitted, verified, and accepted, publish it to the entire
preservation network. This step adds the AU to the whole-network titlesdb database and
notifies the nodes on the preservation network that it is ready to be ingested for
preservation.

Usage:

	adpn publish gitlab:<ISSUEREFERENCE> [--dry-run]
	adpn publish [<FILE>] [--dry-run]
	cat <FILE> | adpn publish - [--dry-run]

Options:
--dry-run   	display SQL script to publish AU to whole network but do not execute

For example:

	adpn publish 'gitlab:adpnet/adpn---general#77'
	
adpn publishers
---------------
List and manage the available list of publishers who may submit AUs for preservation
in ADPNet. (These may be ADPNet Members or they may be ADPNet Hosts.)

adpn publisher list
-------------------
Provide a list of current publishers and alphanumeric codes used to refer to them.

Usage:

	adpn publisher list
	
adpn publisher add
------------------
Add a new publisher code to the list of publishers on the ADPNet props server.

Usage:

	adpn publisher add [<AU_PUB_ID>] [<PUBLISHER_NAME>]
	
For example:

	adpn publisher add TSK "Tuskegee University Archives"
	
adpn plugins
------------
List available plugins or provide details on a given plugin and its required parameters.

Set up your LOCKSS Daemon information in `adpnet.json` or provide it on the command line
using --daemon=<HOST> --user=<USER> --proxy=<PROXYHOST> --port=<PROXYPORT> etc.

adpn plugins list
-----------------
To list available plugins:

	./adpn plugins list --plugin-keywords="Auburn University"

gets you a list of all plugins whose names contain the keywords "Auburn" and "University"

	./adpn plugins list --plugin-regex=".*Directory.*"

gets you a list of all plugins whose names match the regex ".*Directory.*"

adpn plugins details
--------------------
To output detailed information about a selected plugin:

	./adpn plugins details --jar="http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar"
	./adpn plugins details --plugin-id=" gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin"
	
If a wildcard match (`--plugin-keywords="..."` or `--plugin-regex="..."`) matches exactly
one plugin, you can also use the wildcard:

	./adpn plugins details --plugin-keywords="Department Directory"
	./adpn plugins details --plugin-regex="Auburn.*Directory.*"

adpn-ingest-test
================
	
	Usage: ./adpn-ingest-test [--daemon=<HOST>] [--user=<USER>] [--pass=<PASSWORD>]
		[--proxy=<PROXYHOST>] [--port=<PROXYPORT>] [--tunnel=<TUNNELHOST>]
		[--plugin=<NAME>|--plugin-regex=<PATTERN>|--plugin-keywords=<WORDS>|--plugin-id=<ID>]
		[--au_title=<TITLE>] [--local=<PATH>|--remote|--help]
		[--<KEY>=<FIELD> ...]

On the publisher's side, to get data needed for the content to ingest:
----------------------------------------------------------------------
0. 	Create a adpn-ingest-test.defaults.conf file containing the following parameters,
	in plain text, one per line. Place in the same subdir as the adpn-ingest-test script.
	
		--daemon=<HOST:PORT>
		--user=<USERNAME>
	
	If you need to connect to the LOCKSS props server through a SOCKS5 proxy, include:
	
		--proxy=<HOST>
		--port=<PORT>
		
	If you need to use SSH tunneling to connect to the SOCKS5 proxy, use:
	
		--proxy=localhost
		--port=<PORT>
		--tunnel=<SSH HOST>
		
	If there is a default plugin that you will use for most of your ingests, add:
	
		--plugin-id=<ID>
		
	If the plugin has one or more parameters which stay the same across different ingests,
	add something like:
	
		--<PARAMETER>=<VALUE>
		
	For example:
	
		--base_url=http://archives.alabama.gov/Lockss/
		
1. 	Run the script, providing specific parameters on the command line (or enter them at
	the console):
	
		./adpn-ingest-test --local="w:\File\Location" --au_title="Archival Unit Name"

	If you are using a different plugin from the one specified in your conf file:
	
		./adpn-ingest-test --local="w:\File\Location" --au_title="Archival Unit Name" --plugin="Plugin Name"
		
2. 	If there are required parameters for the plugin that aren't specified in your conf file
	you will be prompted for them at the console. After you've filled in any/all required
	parameters, you'll get a report something like this:
	
		INGEST INFORMATION AND PARAMETERS:
		----------------------------------
		INGEST TITLE:   WPA Folder 01
		FILE SIZE :     2.1G (2,243,154,758 bytes, 689 files)
		PLUGIN JAR:     http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar
		PLUGIN ID:      gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin
		PLUGIN NAME:    Alabama Department of Archives and History Directory Plugin
		PLUGIN VERSION: 1
		BASE URL:       base_url="http://archives.alabama.gov/Lockss/"
		SUBDIRECTORY:   subdirectory="WPA-Folder-01"

		JSON PACKET:    {"Ingest Title": "WPA Folder 01", "File Size ": "2.1G (2,243,154,758 bytes, 689 files)", "Plugin JAR": "http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar", "Plugin ID": "gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin", "Plugin Name": "Alabama Department of Archives and History Directory Plugin", "Plugin Version": "1", "Start URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "Manifest URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "Base URL": "base_url=\"http://archives.alabama.gov/Lockss/\"", "Subdirectory": "subdirectory=\"WPA-Folder-01\"", "au_name": "Alabama Department of Archives and History Directory Plugin, Base URL http://archives.alabama.gov/Lockss/, Subdirectory WPA-Folder-01", "au_start_url": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "au_manifest": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "parameters": [["base_url", "http://archives.alabama.gov/Lockss/"], ["subdirectory", "WPA-Folder-01"]]}

		URL RETRIEVAL TESTS:
		--------------------
		200      OK      au_start_url    http://archives.alabama.gov/Lockss/WPA-Folder-01/       "%s%s/", base_url, subdirectory
		200      OK      au_manifest     http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html      "%s%s/manifestpage.html", base_url, subdirectory

3.	Copy and paste the report into an e-mail and send it to the LOCKSS network administrator.
	
On the LOCKSS network administrator's side, to run tests prior to ingesting:
----------------------------------------------------------------------------

0. 	Create a adpn-ingest-test.defaults.conf file containing the usual parameters,
	in plain text, one per line. Place in the same subdir as the adpn-ingest-test script.
	
1. 	Run the script, providing specific parameters by pasting in a JSON packet from your
	user's e-mail.
	
		./adpn-ingest-test - --remote=1

	Paste in the "JSON PACKET" line from the e-mail and press Ctrl-D at the end.
	
2. 	You should get a report back which looks something like this:

		INGEST INFORMATION AND PARAMETERS:
		----------------------------------
		INGEST TITLE:   WPA Folder 01
		PLUGIN JAR:     http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar
		PLUGIN ID:      gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin
		PLUGIN NAME:    Alabama Department of Archives and History Directory Plugin
		PLUGIN VERSION: 1
		BASE URL:       base_url="http://archives.alabama.gov/Lockss/"
		SUBDIRECTORY:   subdirectory="WPA-Folder-01"

		JSON PACKET:    {"Ingest Title": "WPA Folder 01", "Plugin JAR": "http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar", "Plugin ID": "gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin", "Plugin Name": "Alabama Department of Archives and History Directory Plugin", "Plugin Version": "1", "Start URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "Manifest URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "Base URL": "base_url=\"http://archives.alabama.gov/Lockss/\"", "Subdirectory": "subdirectory=\"WPA-Folder-01\"", "au_name": "Alabama Department of Archives and History Directory Plugin, Base URL http://archives.alabama.gov/Lockss/, Subdirectory WPA-Folder-01", "au_start_url": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "au_manifest": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "parameters": [["base_url", "http://archives.alabama.gov/Lockss/"], ["subdirectory", "WPA-Folder-01"]]}

		URL RETRIEVAL TESTS:
		--------------------
		200      OK      au_start_url    http://archives.alabama.gov/Lockss/WPA-Folder-01/       "%s%s/", base_url, subdirectory
		200      OK      au_manifest     http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html      "%s%s/manifestpage.html", base_url, subdirectory

