Utility scripts for extracting and reporting information about ADPNet (LOCKSS) Publisher
Plugins, transmitting information about Archival Units (AU) staged for ingest into the
network, testing the availability of the AU content, and automating the process of
inserting the AU into the network titles list.

Main tools:

* `adpn`: master script, command-line interface to common operations including stage, ingest, and publish
* `adpn-ingest-test`: bash script to coordinate tests when staging content into ADPNet
* `adpn-ingest-into-titlesdb.py`: Python script to add a staged AU to the titlesdb MySQL database
* `adpn-titlesdb-diff`: bash script to test before/after state of the titlesdb XML listing

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

adpn-ingest-test
================
	
	Usage: ./adpn-ingest-test [--daemon=<HOST>] [--user=<USER>] [--pass=<PASSWORD>]
		[--proxy=<PROXYHOST>] [--port=<PROXYPORT>] [--tunnel=<TUNNELHOST>]
		[--plugin=<NAME>|--plugin-regex=<PATTERN>|--plugin-keywords=<WORDS>|--plugin-id=<ID>]
		[--au_title=<TITLE>] [--local=<PATH>|--remote|--plugin-details|--help]
		[--<KEY>=<FIELD> ...]

Development started in May 2019 by Charles Johnson, Collections Archivist,
Alabama Department of Archives and History (<charlesw.johnson@archives.alabama.gov>).

All the original code in here is hereby released into the public domain. Any code copied
or derived from other public sources is noted in comments, and is governed by the
licensing terms preferred by the authors of the original code. (CJ, 2019/05/23)

To get basic information about a given plugin:
----------------------------------------------
Set up your LOCKSS Daemon information in the adpn-ingest-test.defaults.conf file
(described below) or provide it on the command line using --daemon=<HOST> --user=<USER>
--proxy=<PROXYHOST> --port=<PROXYPORT> etc.

	./adpn-ingest-test --plugin-details --plugin-keywords="Auburn University"

gets you a list of all plugins whose names contain the keywords "Auburn" and "University"

	./adpn-ingest-test --plugin-details --plugin-regex=".*Directory.*"


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

