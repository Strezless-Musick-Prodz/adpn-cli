Utility scripts for extracting and reporting information about ADPNet (LOCKSS) Publisher
Plugins.

	lockss-ingest-test: bash script to coordinate tests  when staging content into ADPNet
	
	Usage: ./lockss-ingest-test [--daemon=<HOST>] [--user=<USER>] [--pass=<PASSWORD>]
		[--proxy=<PROXYHOST>] [--port=<PROXYPORT>] [--plugin=<NAME>|--plugin-regex=<PATTERN>]
		[--au_title=<TITLE>] [--local=<PATH>] [--<KEY>=<FIELD> ...]
		
Development started in May 2019 by Charles Johnson, Collections Archivist,
Alabama Department of Archives and History (<charlesw.johnson@archives.alabama.gov>).

All the original code in here is hereby released into the public domain. Any code copied
or derived from other public sources is noted in comments, and is governed by the
licensing terms preferred by the authors of the original code. (CJ, 2019/05/23)
