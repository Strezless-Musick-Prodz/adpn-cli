#!/usr/bin/python3
#
# adpn-stage-content.py: upload a directory of files for preservation to a staging server
# accessible via FTP, easy-peasy lemon squeezy.
#
# @version 2021.0823

import io, os, sys
import fileinput, stat
import re, json, numbers
import urllib, ftplib, pysftp, paramiko.agent
import math, binascii
from paramiko import ssh_exception
from datetime import datetime
from io import BytesIO
from ftplib import FTP
from getpass import getpass, getuser
from myLockssScripts import myPyCommandLine, myPyJSON, align_switches, shift_args
from ADPNPreservationPackage import ADPNPreservationPackage, myLockssPlugin
from ADPNCommandLineTool import ADPNCommandLineTool, ADPNScriptPipeline
from myFTPStaging import myFTPStaging
from contextlib import contextmanager

python_std_input = input
def input (*args) :
    old_stdout = sys.stdout
    try :
        sys.stdout = sys.stderr
        return python_std_input(*args)
    finally :
        sys.stdout = old_stdout

class ADPNStagingArea :

    def __init__ (self, protocol="sftp", host="localhost", user=None, passwd=None, identity=None, base_dir="/", subdirectory=None, authentication=None, getpass=lambda x: None, dry_run=False, skip_download=False) :
        self.protocol = protocol
        self.host = host
        self.user = user
        self.passwd = passwd
        self.identity = identity
        self.base_dir = base_dir
        self.subdirectory = subdirectory
        self.key_protocols = [ "sftp", "scp" ]
        self.authentication = authentication
        self._agent = None
        self.getpass = getpass
        self._dry_run = dry_run
        self.skip_download = skip_download
        
    @property
    def dry_run (self) :
        return self._dry_run
        
    @dry_run.setter
    def dry_run (self, rhs) :
        self._dry_run = rhs

    @property
    def account (self) :
        return ( "%(user)s@%(host)s" % { "user": self.user, "host": self.host } )
    
    @property
    def agent (self) :
        if self._agent is None :
            try :
                self._agent = paramiko.agent.Agent()
            except ssh_exception.SSHException as e :
                # if we cannot talk to the agent, that's like having no agent
                pass
        return self._agent

    @property
    def agent_keys (self) :
        keys = []
        if self.agent is not None :
            # use: ( key, get_password )
            keys = [ ( key, lambda: None ) for key in self.agent.get_keys() ]
        return keys

    @property
    def private_keys (self) :
        all_keys = self.agent_keys
        if self.has_private_keyfile() :
            # use: ( key, get_password )
            all_keys.append( ( self.get_private_keyfile(), lambda: self.read_password(keyfile=True, passwd=self.passwd) ) )
        return all_keys
    
    @property
    def authentication_credentials (self) :
        creds = [ ( lambda: None, key, get_passphrase ) for (key, get_passphrase) in self.private_keys ]
        creds.append( ( lambda: self.read_password(keyfile=False, passwd=self.passwd), None, lambda: None ) )
        return creds
    
    @property
    def getpass (self) :
        return self._getpass
    
    @getpass.setter
    def getpass (self, callback) :
        self._getpass = callback
    
    def read_password (self, keyfile=None, passwd=None) :
        prompt = self.get_password_prompt(keyfile=keyfile)
        passwd = passwd if passwd is not None else self.passwd
        return passwd if passwd is not None else self.getpass(prompt)
    
    def accept_url(self, url) :
        (host, user, passwd, base_dir, subdirectory) = (None, None, None, None, None)
        
        bits=urllib.parse.urlparse(url)
        if len(bits.scheme) > 0 :
            self.protocol = bits.scheme
        
        if len(bits.netloc) > 0 :
            netloc = bits.netloc.split('@', 1)
            netloc.reverse()
            (host, credentials)=(netloc[0], netloc[1] if len(netloc) > 1 else None)
            credentials=credentials.split(':', 1) if credentials is not None else [None, None]
            (user, passwd) = (credentials[0], credentials[1] if len(credentials) > 1 else None)
        
            self.host = host
            self.user = user
            self.passwd = passwd
        
        if len(bits.path) > 1 :
            base_dir = bits.path
            subdirectory = None
            
            self.base_dir = base_dir
            self.subdirectory = subdirectory
    
    def is_sftp (self) :
        return ( "sftp" == self.protocol )

    def uses_keyfile (self) :
        return ( self.protocol in self.key_protocols )

    def get_private_keyfile (self) :
        keyfile = None
        
        if self.uses_keyfile() :
            
            # do we have an explicitly specified identity / key file?
            if self.identity is not None :
                candidate_paths = [ os.path.realpath(os.path.expanduser(self.identity)) ]
                
            # can we figure out an implicit identity / key file based on defaults?
            else :
                candidates = [ "id_rsa", "id_dsa", "identity" ]
                ssh_dir = os.path.expanduser("~/.ssh")
                candidate_paths = [ os.path.join(os.path.expanduser(ssh_dir), candidate) for candidate in candidates ]
                
            keyfiles = [ path for path in candidate_paths if os.path.exists(path) ]
            
            if len(keyfiles) > 0 :
                keyfile = keyfiles[0]
            
        return keyfile
        
    def has_private_keyfile (self) :
        return ( self.authentication != "password" ) and ( self.get_private_keyfile() is not None )
        
    def get_password_prompt (self, protocol=None, keyfile=None) :
        protocol = protocol if protocol is not None else self.protocol
        keyfile = keyfile if keyfile is not None else self.has_private_keyfile()
        what = "private key passphrase" if keyfile else "password"
        return "%(protocol)s %(what)s (%(user)s@%(host)s): " % {"protocol": protocol.upper(), "what": what, "user": self.user, "host": self.host}
        
    def open_connection (self) :
        if self.is_sftp() :
            
            # first check to see whether we can establish a connection using key pair authentication
            conn = None
            errs = []
            i = 0
            for ( get_passwd, private_key, get_private_key_pass ) in self.authentication_credentials :
                try :
                    if conn is None :
                        i = i+1
                        
                        ( passwd, private_key_pass ) = ( get_passwd(), get_private_key_pass() )
                        
                        credentials=""
                        if type(private_key) is paramiko.agent.AgentKey :
                            credentials = ( "agent key(%(key)s)" % {
                            "key": binascii.hexlify(private_key.get_fingerprint(), sep=":").decode("utf-8")
                            } )
                        elif private_key_pass is not None :
                            credentials = ( "private key(%(key)s, %(pass)s)" % {
                            "key": private_key if type(private_key) is str else "<AGENT KEY>",
                            "pass": "*" * len(private_key_pass) if private_key_pass is not None else "<NONE>"
                            } )
                        else :
                            credentials = ( "password(%(pass)s)" % {
                            "pass": "*" * len(passwd) if passwd is not None else "<NONE>"
                            } )
                        #credentials = "key:%(key)/"
                        print("* %(protocol)s connection attempt %(i)d, %(user)s@%(host)s < %(credentials)s" % {
                            "protocol": self.protocol.upper(),
                            "i": i,
                            "user": self.user,
                            "host": self.host,
                            "credentials": credentials,
                        }, file=sys.stderr)
                        
                        conn = pysftp.Connection(
                            self.host, username=self.user,
                            password=passwd,
                            private_key=private_key, private_key_pass=private_key_pass
                        )
                    
                except ValueError as e :
                    errs.append(e)
                except ssh_exception.AuthenticationException as e :
                    errs.append(e)
                except ssh_exception.SSHException as e :
                    errs.append(e)
            
            if conn is None :
            # apparently we could not connect using any means that we could figure out
            # so let's return a pile of exceptions indicating what all we tried
                raise paramiko.ssh_exception.NoValidConnectionsError( { ( self.host, 22 ): errs } )
                
        else :
            conn = FTP(self.host, user=self.user, passwd=self.passwd)
        
        return myFTPStaging(conn, user=self.user, host=self.host, dry_run=self.dry_run, skip_download=self.skip_download) if conn is not None else None

class ADPNPublisher :
    
    def __init__ (self, switches={}) :
        self._switches = switches
    
    @property
    def switches (self) :
        return self._switches
    
    def to_dict (self) :
        return { "name": self.name, "code": self.code }
    
    @property
    def code (self) :
        code = self.switches.get('publisher') if 'publisher' in self.switches else self.switches.get('peer')
        return code.upper() if type(code) is str else code
    
    @property
    def name (self) :
        name = self.switches.get('institution') if 'institution' in self.switches else None
        return name
    
    @property
    def name_code (self) :
        pattern = "%(name)s (%(code)s)" if self.code is not None else "%(name)s"
        return ( pattern % self.to_dict() )
    
class ADPNStageContentScript(ADPNCommandLineTool) :
    """
Usage: adpn-stage-content.py [<OPTIONS>]... [<URL>]

URL should be an SFTP or FTP URL, in the form:
    sftp://[<USER>[:<PASS>]@]<HOST>/<DIR>
    ftp://[<USER>[:<PASS>]@]<HOST>/<DIR>
<USER> and <PASS> elements are optional; they can be provided as part of the URL,
or using command-line switches, or interactively at input and password prompts.

  --local=<PATH>   	the local directory containing the files to stage
  --au_title=<TITLE>   	the human-readable title for the contents of this AU
  --subdirectory=<SLUG>	the subdirectory on the staging server to hold AU files
  --directory=<SLUG>   	identical to --subdirectory
  --backup=<PATH>      	path to store current contents (if any) of staging location
  
Output and Diagnostics:

  --output=<MIME>      	text/plain or application/json
  --verbose=<LEVEL>   	level (0-2) of diagnostic output during FTP upload/download
  --quiet             	identical to --verbose=0
  
Common configuration parameters:

  --base_url=<URL>     	WWW: the URL for web access to the staging area
  --host=<NAME>        	FTP: host name of the server with the staging area
  --user=<NAME>        	FTP: username for logging in to the staging server
  --pass=<PASSWD>      	FTP: password for logging in to the staging server
  --base_dir=<PATH>   	FTP: path to the staging area on the FTP server

Default values for these parameters can be set in the JSON configuration file
adpnet.json, located in the same directory as the script. To set a default
value, add a key-value pair to the hash table with a key based on the name of
the switch. (For example, to set the default value for the --institution switch
to "Alabama Department of Archives and History", add the following pair to the
hash table:

    {
        ...
        "institution": "Alabama Department of Archives and History",
        ...
    }
    
The default values in adpnet.json are overridden if values are provided on the
command line with explicit switches.
    """
    
    def __init__ (self, scriptpath, argv, switches, scriptname=None) :
        super().__init__(scriptpath=scriptpath, argv=argv, switches=switches, scriptname=scriptname)
        
        self.pipes = ADPNScriptPipeline(conditional=True)
        self.switches=self.pipes.backfilled(self.switches, 'local', 'Packaged In')
        self.switches=self.pipes.backfilled(self.switches, 'remote', 'Staged To')
        self.switches=self.pipes.backfilled(self.switches, 'au_file_size', 'File Size')
        self.switches=self.pipes.backfilled(self.switches, 'au_title', 'AU Package')
        self.switches=self.pipes.backfilled(self.switches, 'au_title', 'Ingest Title')
        self.switches=self.pipes.backfilled(self.switches, 'ingest_title', 'Ingest Title')
        self.switches=self.pipes.backfilled(self.switches, 'directory', '@directory')
        self.switches=self.pipes.backfilled(self.switches, 'subdirectory', '@directory')
        self.switches=self.pipes.backfilled(self.switches, 'directory', '@subdirectory')
        self.switches=self.pipes.backfilled(self.switches, 'subdirectory', '@subdirectory')
        
        args = argv[1:]
    
        # look for positional arguments: first argument goes to --local=...
        if switches.get('local') is None :
            if len(args) > 0 :
                ( switches['local'], args ) = shift_args(args)
        # look for positional arguments: next argument goes to --remote=...
        if switches.get('remote') is None :
            if len(args) > 0 :
                ( switches['remote'], args ) = shift_args(args)
        align_switches("remote", "stage/base", switches)
        
        self.verbose=(0 if self.switches.get('quiet') else self.switches.get('verbose'))
        
        # start out with defaults
        self.ftp = None
        self.stage = ADPNStagingArea(getpass=getpass)
        self.publisher = ADPNPublisher(switches)
        self._package = None
        
        # now unpack and overlay elements from the SFTP/FTP URL, if any is provided
        stage_base = self.switches.get('stage/base') if self.switches.get('stage/base') is not None else None
        if stage_base is not None :
            self.stage.accept_url(stage_base)
        
        # now overlay any further values from the command-line switches, if provided
        self.stage.protocol=self.switches.get('protocol') if self.switches.get('protocol') is not None else self.stage.protocol
        self.stage.host=self.switches.get('host') if self.switches.get('host') is not None else self.stage.host
        self.stage.user=self.switches.get('user') if self.switches.get('user') is not None else self.stage.user
        self.stage.passwd=self.switches.get('pass') if self.switches.get('pass') is not None else self.stage.passwd
        self.stage.base_dir=self.switches.get('base_dir') if switches.get('base_dir') is not None else self.stage.base_dir
        self.stage.identity=self.switches.get('identity') if self.switches.get('identity') is not None else self.stage.identity
        self.stage.subdirectory=self.subdirectory_switch if self.subdirectory_switch is not None else self.stage.subdirectory
        self.stage.authentication=self.get_authentication_method()
    
    @property
    def subdirectory_switch (self) :
        return self.switches.get('directory') if switches.get('directory') is not None else self.switches.get('subdirectory')
        
    @subdirectory_switch.setter
    def subdirectory_switch (self, rhs) :
        self.switches['subdirectory'] = rhs
        self.switches['directory'] = rhs
    
    def get_locallocation (self) :
        return os.path.realpath(self.switches.get('local')) if self.switches.get('local') else os.getcwd()
        
    def get_authentication_method (self) :
        if not self.stage.uses_keyfile() :
            method = "password"
        elif self.switches.get("authentication") is not None :
            method = self.switches.get("authentication")
        elif self.switches.get("password") is not None :
            method = "password"
        else :
            method = None
        return method
        
    @property
    def package (self) :
        return self._package
    
    @package.setter
    def package (self, rhs) :
        self._package = rhs
    
    def get_itemparent (self, file) :
        canonical = os.path.realpath(file)
        return os.path.dirname(canonical)

    def get_username (self) :
        return self.switches.get("user/realname", None) if self.switched("user/realname") else getuser()
    
    def get_email (self) :
        return self.switches.get("user/email", None) if self.switched("user/email") else self.stage.account
    
    def get_emailname (self) :
        return ( "%(realname)s <%(email)s>" % { "realname": self.get_username(), "email": self.get_email() } )
        
    def new_backup_dir (self) :
        backupPath=self.switches.get('backup')
        
        if not self.switched('dry-run') :
            try :
                os.mkdir(backupPath)
            except FileExistsError as e :
                pass
            
            datestamp=datetime.now().strftime('%Y%m%d%H%M%S')
            backupPath="%(backup)s/%(date)s" % {"backup": backupPath, "date": datestamp}
            
            try :
                os.mkdir(backupPath)
            except FileExistsError as e :
                pass

            backupPath="%(backup)s/%(subdirectory)s" % {"backup": backupPath, "subdirectory": self.subdirectory_switch}
            try :
                os.mkdir(backupPath)
            except FileExistsError as e :
                pass
        
        return backupPath
    
    def exclude_filesystem_artifacts (self, file) :
        return file.lower() in ['thumbs.db']
        
    def establish_connection (self, interactive=True, dry_run=False) :
        if self.stage.user is None :
            self.stage.user = input("User: ")
        self.stage.dry_run = dry_run
        self.stage.skip_download = self.test_skip('backup')
        
        conn = None
        try :
            conn = self.stage.open_connection()
        except ssh_exception.NoValidConnectionsError as e :
            self.write_error(1, "%(protocol)s connection failure: %(message)s. Attempts:" % { "protocol": self.stage.protocol.upper(), "message": e.args[1] })
            for ( addr, errs ) in e.errors.items() :
                for err in errs :
                    err_message = str(err)
                    self.write_error(1, "%(host)s:%(port)d: %(err_message)s" % { "host": addr[0], "port": addr[1], "err_message": err_message })
                    
        except ValueError as e :
            if len(self.stage.passwd) == 0 :
                settings = { "protocol": self.stage.protocol.upper(), "key": self.stage.get_private_keyfile(), "err": str(e) }
                self.write_error(1, "%(protocol)s key failure. Did you use the right passphrase for the key [%(key)s]?" % settings)
            else :
                raise
        except ssh_exception.AuthenticationException as e :
            settings = { "protocol": self.stage.protocol.upper(), "key": self.stage.get_private_keyfile(), "err": str(e) }
            if self.stage.has_private_keyfile() :
                self.write_error(1, "%(protocol)s authentication failure. Did you use the right key file [%(key)s]?" % settings )
            else :
                self.write_error(1, "%(protocol)s authentication failure. Did you use the right password?" % settings )
        except ssh_exception.SSHException as e :
            settings = { "protocol": self.stage.protocol.upper(), "key": self.stage.get_private_keyfile(), "err": str(e) }
            if self.stage.has_private_keyfile() :
                self.write_error(1, "%(protocol)s key failure. Did you use the right passphrase for the key [%(key)s]?" % settings)
            else :
                self.write_error(1, "%(protocol)s connection failed: %(err)s." % settings)
        
        self.ftp = conn
        assert self.ftp is not None, { "message": ("Connection failed for %(user)s@%(host)s" % {"user": self.stage.user, "host": self.stage.host}), "code": 1 }
        

    def output_status (self, level, type, arg) :
        (prefix, message) = (type, arg)

        if "ok" == type :
            self.write_output(data=message, json_encode=True, prolog="JSON PACKET:\t")
        else :
            if "uploaded" == type :
                prefix = ">>>" if not self.switched('dry-run') else "(dry-run)>"
            elif "downloaded" == type :
                prefix = "<<<" if not self.switched('dry-run') else "(dry-run)<"
            elif "excluded" == type :
                prefix = "---"
                message = ("excluded %(arg)s" % {"arg": arg})
            elif "chdir" == type :
                prefix = "..."
                path = "./%(dir)s" % {"dir": arg[1]} if arg[1].find("/")<0 else arg[1]
                message = "cd %(path)s" % {"path": path}
            
            self.write_status(message=message, prolog=prefix, is_notice=False, verbosity=level)
    
    def get_human_readable (self, byte_count) :
        return "%.1f %s" % self.get_bytes_order_magnitude(byte_count)
        
    def get_bytes_order_magnitude (self, byte_count) :
        orders = [ 'B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB' ]
        factor = 1024.0
        i = 0
        magnitude = ( byte_count * 1.0 )
        while i < len(orders)-1 and magnitude >= factor :
            i = i + 1
            magnitude = magnitude / factor
        return (magnitude, orders[i])
    
    def get_plugin_parameters (self) :
        plugin = myLockssPlugin(jar=self.switches["jar"])
        plugin_parameter_names = [ parameter["name"] for parameter in plugin.get_parameter_keys() ]
        plugin_parameters = [ [parameter, setting] for (parameter, setting) in self.switches.items() if parameter in plugin_parameter_names ]
        return (plugin, plugin_parameters)
        
    def get_au_title (self) :
        return self.switches.get('au_title') if self.switched('au_title') else self.subdirectory_switch
    
    def get_au_start_url (self) :
        au_start_url = None
        
        details_list = self.package.plugin.get_details(check_parameters=True) # bolt on missing parameter(s)
        details = {}
        for detail in details_list :
            details[detail['name']] = detail['value']
        au_start_url = details['Start URL']
        return au_start_url
    
    def do_set_location (self) :
        # Let's CWD over to the repository
        try :
            self.ftp.set_remotelocation(self.stage.base_dir)
        except FileNotFoundError as e :
            raise AssertionError( { "message": ("Failed to set remote directory location: %(base_dir)s" % { "base_dir": self.stage.base_dir } ), "code": 1} ) from e
            

    def do_download_to (self, directory) :
        try :
            (local_pwd, remote_pwd) = self.ftp.set_location(dir=directory, remote=self.stage.subdirectory, make=True)
            self.ftp.download(file=".", exclude=self.exclude_filesystem_artifacts, notification=self.output_status)
        except FileNotFoundError as e :
            if self.ftp.dry_run :
                pass
            else :
                raise
        return (local_pwd, remote_pwd)
    
    def do_upload_to (self, local, remote) :
        try :
            self.ftp.set_location(dir=local, remote=remote)
            (local_pwd, remote_pwd) = self.ftp.set_location(dir=self.get_locallocation(), remote=self.stage.subdirectory, make=True)
            self.output_status(2, "chdir", (os.getcwd(), self.ftp.get_location()))
        except FileNotFoundError as e :
            if self.ftp.dry_run :
                pass
            else :
                raise
        
        # upload the present directory recursively
        self.ftp.upload(file=".", exclude=self.exclude_filesystem_artifacts, notification=self.output_status)
        
        return (local_pwd, remote_pwd)
    
    def do_transfer_files (self) :
        (local_pwd, remote_pwd) = self.ftp.get_location(local=True, remote=True)
            
        if not self.test_skip("download") :
            (local_pwd, remote_pwd) = self.do_download_to(directory=self.new_backup_dir())
            
        if not self.test_skip("upload") :
            (local_pwd, remote_pwd) = self.do_upload_to(local=local_pwd, remote=remote_pwd) 
    
    def confirm_local_packaging (self) :
        # Let's determine the plugin and its parameters from the command line switches
        (plugin, plugin_parameters) = self.get_plugin_parameters()
            
        # Now let's plug the parameters for this package in to the package and plugin
        self.package = ADPNPreservationPackage(
            path=self.get_locallocation(),
            plugin=plugin, plugin_parameters=plugin_parameters,
            switches=self.switches
        )

        # Now let's check the packaging
        if not self.test_skip("package") :
            assert self.package.has_bagit_enclosure(), { "message": "%(path)s must be packaged in BagIt format" % { "path": self.package.get_path(canonicalize=True) }, "remedy": "adpn package", "code": 2 }
            assert self.package.has_valid_manifest(), { "message": "%(path)s must be packaged with a valid LOCKSS manifest" % { "path": self.package.get_path(canonicalize=True) }, "remedy": "adpn package", "code": 2 }

    def execute (self, terminate=True) :
        super().execute(terminate=False)
        
        try :
            if self.stage.base_dir is None or len(self.stage.base_dir) == 0:
                self.stage.base_dir = input("Base dir: ")
            if self.stage.subdirectory is None or len(self.stage.subdirectory) == 0 :
                self.subdirectory_switch = os.path.basename(self.get_locallocation())
                self.stage.subdirectory = self.subdirectory_switch
            
            try :
                if not self.switched('volume') :
                    self.confirm_local_packaging()
                
                # Let's log in to the host
                self.establish_connection(dry_run=self.switched('dry-run'))
                self.do_set_location()
                
                if self.switched('volume') :
                    vol = self.ftp.get_volume()
                    
                    human_readable = dict([ (re.sub(r"bytes_", "space_", key), self.get_human_readable(value)) for (key, value) in vol.items() if re.match(r".*(bytes_.)*", key) ])
                    out_packet = { **vol, **human_readable }
                else :
                    self.do_transfer_files()

                    # Pack up JSON data for output
                    piped_data = ( {} if self.pipes.get_data() is None else self.pipes.get_data() )
                    script_data = {
                        "Ingest Step": self.switches.get('step'),
                        self.switches.get('label-by'): self.get_emailname(),
                        self.switches.get('label-to'): self.stage.account,
                    }
                    out_packet = self.package.get_pipeline_metadata(cascade={
                        **piped_data, **script_data
                    }, read_manifest=True)
                    
                    if self.switched('unstage') :
                        out_packet.pop('Packaged In', None)
                    
                # Send JSON data output to stdout/pipeline
                self.output_status(0, "ok", out_packet)

            except FileNotFoundError  as e :
                self.write_error(1, "Local preservation package not found: '%(file)s' (%(msg)s)" % { "file": e.filename, "msg": e.args[1] } )

        except AssertionError as e : # Parameter or precondition requirements failure
            if len(e.args) > 0 and type(e.args[0]) is dict :
                err = e.args[0]
                code = err['code'] if 'code' in err else 2
                message = ( "REQUIRED: %(message)s; try `%(remedy)s`" if "remedy" in err else "FAILED: %(message)s.") % err
                self.write_error(code, message)
            elif len(e.args) == 2 :
                ( message, req ) = e.args
                missing = [ parameter for parameter in req if self.switches.get(parameter) is None ]
                self.write_error(2, "Required parameter missing: %(missing)s" % { "missing": ", ".join(missing) })
            else :
                ( message, req ) = ( e.args[0], None )
                self.write_error(2, "Requirement failure: %(message)s" % { "message": message })
        
        except KeyboardInterrupt as e :
            self.write_error(255, "Keyboard Interrupt.", prefix="^C\n")

        finally :
            try :
                if self.ftp is not None :
                    self.ftp.quit()
            except ftplib.error_perm as e :
                pass
        
        if terminate :
            self.exit()
        
if __name__ == '__main__':
    scriptpath = os.path.realpath(sys.argv[0])
    scriptname = os.path.basename(scriptpath)
    scriptdir = os.path.dirname(sys.argv[0])
    configjson = "/".join([scriptdir, "adpnet.json"])
    
    os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
    
    defaults={
            "dry-run": False, "unstage": False,
            "ftp/host": None, "ftp/user": None, "ftp/pass": None,
            "stage/base": None, "stage/host": None, "stage/user": None, "stage/pass": None, "stage/protocol": None,
            "stage/identity": None, "identity": None,
            "stage/authentication": None, "authentication": None, "password": None,
            "user/realname": None, "user/email": None,
            "jar": None,
            "subdirectory": None, "directory": None,
            "base_dir": None, "output": "text/plain",
            "remote": None, "local": None, "backup": os.path.expanduser("~/backup"),
            "verbose": 1, "quiet": False,
            "base_url": None, "stage/base_url": None,
            "au_title": None, "au_notes": None, "au_file_size": None, "institution": None,
            "skip": None,
            "proxy": None, "port": None, "tunnel": None, "tunnel-port": None,
            "context": scriptname
    }
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults=defaults, configfile=configjson, settingsgroup=["stage", "ftp", "user"]).parse()
    
    align_switches("identity", "stage/identity", switches)
    align_switches("authentication", "stage/authentication", switches)
    align_switches("directory", "subdirectory", switches)
    align_switches("base_url", "stage/base_url", switches)
    
    # These defaults are conditional on the absence/presence of the --unstage flag:
    unstaging=( switches.get('unstage') )
    step_defaults={
        "step": "staged" if not unstaging else "unstaged",
        "label-by": "Staged By" if not unstaging else "Unstaged By",
        "label-to": "Staged To" if not unstaging else "Unstaged From"
    }
    switches={ **step_defaults, **switches }
    defaults={ **defaults, **step_defaults }
    
    if unstaging :
        switches['skip'] = ( switches.get('skip') + "," if switches.get('skip') else '' ) + "package"
    
    script = ADPNStageContentScript(scriptpath, sys.argv, switches, scriptname=switches.get('context'))
    
    if script.switched('details') :
        print("FROM:", switches['local'], file=sys.stderr)
        print("TO:", switches['remote'], file=sys.stderr)
        if script.switches.get('details') in switches and script.switches.get('details') != 'details' :
            print(script.switches.get('details'), ": ", switches.get(script.switches.get('details')), file=sys.stderr)
        print("", file=sys.stderr)
        print("All Settings:", switches, file=sys.stderr)
        print("", file=sys.stderr)
        print("Defaults:", defaults, file=sys.stderr)
    else :
        script.execute()

    script.exit()
    