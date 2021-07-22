#!/usr/bin/python3
#
# ADPNPreservationPackage.py: provide the ADPNPreservationPackage class, an encapsulation of
# some operations dealing with packaging directories of files into AUs for ADPNet
#
# @version 2021.0629

import io, os, sys, stat
import fileinput
import subprocess
import json, re
import urllib
from myLockssScripts import myADPNScriptSuite, myPyJSON

scripts = myADPNScriptSuite(__file__)

class myLockssPlugin :
    
    def __init__ (self, jar, parameters=None, switches=None) :
        self._parameters = {}
        self.set_parameters(parameters)
        self._switches = ( switches if switches is not None else {} )
        self._switches = { **{ "local": None, "proxy": None, "port": None, "tunnel": None, "tunnel-port": None }, **self._switches }
        self._jar = jar
    
    @property
    def jar (self) :
        return self._jar
    
    @property
    def switches (self) :
        return self._switches
    
    @switches.setter
    def switches (self, rhs) :
        self._switches = rhs

    def set_switch (self, key, value) :
        self._switches[key] = value

    @property
    def parameters (self) :
        return self._parameters
    
    def get_parameters (self, mapped=False) :
        if mapped :
            params = self.parameters
        else :
            params = [ (key, value) for (key, value) in self.parameters.items() ]
        return params
    
    def get_parameter_keys (self, names=False, descriptions=False) :
        try :
            tsv = self.get_tool_data("adpn-plugin-details.py", parameters={"jar": self.jar})
        except FileNotFoundError as e :
            tsv = []
        mapped = [ {"name": row[1], "description": row[2]} for row in tsv if row[0]=="parameter" ]
        bothneither = ( not ( names or descriptions ) or ( names and descriptions ) )
        justone = "description" if descriptions else "name"
        return mapped if bothneither else [ param[justone] for param in mapped ]
    
    def set_parameters (self, parameters, append=False) :
        results = self._parameters if append else {}
        if parameters is not None :
            if type(parameters) is list or type(parameters) is tuple :
                for parameter in parameters :
                    (key, value) = parameter
                    results[key] = value
            elif type(parameters) is dict :
                for (key, value) in parameters.items() :
                    results[key] = value
            else :
                raise ValueError("Cannot initialize myLockssPlugin.parameters with this value", parameters)
        self._parameters = results
                
    def set_parameter (self, key, value) :
        self.set_parameters( [ (key, value) ], append=True )
    
    def get_details (self, check_parameters=None) :
        parameters = {"jar": self.jar, "parameters": json.dumps(self.get_parameters(mapped=True)), "check_parameters": 1 }
        ok_codes = [ 0 ] if check_parameters else [ 0, 100 ]
        try :
            tsv = self.get_tool_data("adpn-plugin-details.py", parameters=parameters, ok=ok_codes)
        except OSError as e :
            required_parameters = self.get_parameter_keys(names=True)
            if len(required_parameters) > 0 :
                error_message = ( "Required plugin parameters: " + json.dumps(required_parameters) )
                raise AssertionError(error_message, required_parameters) from e
            else :
                error_message = ( "Plugin %(url)s NOT FOUND" % { "url": self.jar } )
                raise AssertionError(error_message) from e
        mapped = [ {"name": row[1], "value": row[2] } for row in tsv if row[0]=="detail" ]
        return mapped
    
    def get_tool_data (self, script, argv=None, parameters=None, ok=[ 0 ], process=None, sep="\t") :
        cmdline = [
            scripts.python(),
            scripts.path(script)
        ]
        if argv is not None :
            cmdline = cmdline + argv
        if parameters is not None :
            cmdline = cmdline + [ ( "--%(key)s=%(value)s" % { "key": key, "value": value } ) for (key, value) in parameters.items() ]
        if len([ output for output in cmdline if re.match("^--output=", output) ]) == 0 :
            cmdline.append("--output=text/tab-separated-values")
            
        pipes = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
        std_out = std_err = pipes.communicate()
        
        if not ( pipes.returncode in ok ) :
            # exit code indicates that an error occurred...
            raise OSError(pipes.returncode, std_err)
        elif len(std_err) :
            # return code is in OK range (no error), but output to stderr
            # we may want to do something with the information...
            pass
        
        if process is None :
            process=lambda blob: [ line.split(sep) for line in re.split("[\r\n]+", blob) if len(line.strip()) ]
        rows = []
        for block in std_out :
            rows = rows + process(block)
        
        return rows
    
    def get_makemanifest_command_line (self, path, manifest_data=None, dry_run=False) :
        cmdline = [
            scripts.path("adpn-make-manifest.py"),
                ( "--jar=%(url)s" % { "url": self.jar } ),
                ( "--local=%(local)s" % { "local": path } )
        ]
        if manifest_data is not None :
            cmdline.append("--parameters=%(json)s" % { "json": json.dumps(manifest_data) })
        if dry_run :
            cmdline.append("--dry-run")
        
        connection_sw = [ 'proxy', 'port', 'tunnel', 'tunnel-port' ]
        cmdline = cmdline + [ "--%(k)s=%(v)s" % { "k": key, "v": self.switches.get(key) } for key in connection_sw if self.switches.get(key) ]
        return cmdline
        
    def get_manifest_filename (self, path=None) :
        filename = "manifest.html"
        s_path = path if path is not None else os.path.realpath(".")
        code = 0
        try :
            cmdline = self.get_makemanifest_command_line(s_path, dry_run=True)
            buf = subprocess.check_output(cmdline, encoding="utf-8")
        except subprocess.CalledProcessError as e :
            code = e.returncode
            buf = e.output
        
        if 0 == code : # OK!
            tsv = [ line.split("\t") for line in re.split("[\r\n]+", buf) ]
            filenames = [ os.path.basename(row[0]) for row in tsv ]
            filename = ( filenames[0] if len(filenames) > 0 else filename )
            
        return filename
    
    def new_manifest (self, path=None, manifest_data={}) :
        try :
            cmdline = self.get_makemanifest_command_line(path, manifest_data)
            buf = subprocess.check_output(cmdline, encoding="utf-8")
        except subprocess.CalledProcessError as e :
            # code = e.returncode
            # buf = e.output
            raise
        return buf

def first_of (items, ok=None) :
    oked = [ item for item in filter(ok, items) ]
    return oked[0] if len(oked)>0 else None
    
class ADPNPreservationPackage :
    
    def __init__ (self, path: str, data={}, plugin_parameters=[], switches={}) :
        self.metadata_filters = {
            "AU Package": lambda x, depth: self.filter_au_package(x, depth),
            "Ingest Title": lambda x, depth: self.filter_ingest_title(x, depth),
            "Packaged In": lambda x, depth: os.path.realpath(x) if type(x) is str else x
        }
        self.metadata = data
        self.switches = switches
        self.path = path if path else self.metadata.get('Packaged In')
        self.plugin_jar = self.metadata.get("Plugin JAR")
        self.parameters = plugin_parameters
        self._plugin = myLockssPlugin(jar=self.plugin_jar, parameters=plugin_parameters, switches=switches)
        
    @property
    def path (self) :
        return self._path
    
    @path.setter
    def path (self, rhs) :
        self._path = os.path.realpath(os.path.expanduser(rhs))
        stat_r = os.stat(self._path)
        assert any([ ok(stat_r.st_mode) for ok in [ stat.S_ISDIR, stat.S_ISREG ] ]), "path must be a readable file or directory"
    
    @property
    def metadata (self) :
        return self._metadata
    
    @metadata.setter
    def metadata (self, rhs: dict) :
        self._metadata = {}
        self.accept_metadata(rhs)
    
    def accept_metadata (self, data: dict) :
        for (key, value) in data.items() :
            self.set_metadata(key, value)
    
    def set_metadata (self, key, value, depth=0) :
        self.metadata[key] = self.get_metadata_value(value, key, depth+1)
    
    def get_metadata_value (self, value, key, depth=0) :
        result = value
        m_filter = self.metadata_filters.get(key)
        if callable(m_filter) :
            result = m_filter(value, depth)
        return result
    
    @property
    def metadata_filters (self) :
        return self._metadata_filters
    
    @metadata_filters.setter
    def metadata_filters (self, rhs: dict) :
        self._metadata_filters = rhs
    
    def get_pipeline_metadata (self, cascade={}, include_plugin=True, read_manifest=False) :
        # Reset items with dynamic components from switches
        self.set_metadata("AU Package", self.au_title)
        self.set_metadata("Packaged In", self.path)
        
        static_data = self.read_manifest_data() if read_manifest else {}
        dynamic_data = {}
        for (key, value) in self.metadata.items() :
            if value is not None :
                dynamic_data[key] = value
        piping = { **static_data, **dynamic_data, **cascade }
        
        head = [ "Ingest Title", "File Size", "From Peer", "Plugin JAR",  "Start URL", "Ingest Step" ]
        foot = [ "Packaged In", "status" ]
        
        if include_plugin :
            plugin_parameter_keys = self.plugin.get_parameter_keys()
            for parameter in plugin_parameter_keys :
                description = re.sub('\s*[(][^)]+[)]\s*$', '', parameter["description"])
                foot.append(description)
            foot.append("parameters")
        
        out = {}
        
        # ORDERING: HEADER
        for key in head :
            value = piping.get(key)
            if value is not None :
                out[key] = value
                piping[key] = None
        
        # ORDERING: BODY
        for (key, value) in piping.items() :
            if not ( key in foot or value is None ) :
                out[key] = value
        
        # ORDERING: FOOTER
        for key in foot :
            value = piping.get(key)
            if not ( value is None ) :
                out[key] = value
        if include_plugin :
            for parameter in self.plugin.get_parameter_keys(names=True) :
                if self.switches.get(parameter) :
                    self.plugin.set_parameter(parameter, self.switches.get(parameter))
            
            plugin_settings = self.plugin.get_parameters(mapped=True)
            for parameter in plugin_parameter_keys :
                description = re.sub('\s*[(][^)]+[)]\s*$', '', parameter["description"])
                out[description] = plugin_settings[parameter["name"]]
            out = { **out, **{ "parameters": self.plugin.get_parameters() } }
        return out
    
    @property
    def switches (self) :
        return self._switches
        
    @switches.setter
    def switches (self, rhs) :
        self._switches = {}
        self.accept_switches(rhs)
    
    def accept_switches (self, switches: dict) :
        for (key, value) in switches.items() :
            self.switches[key] = value
            data_key = self.get_metadata_key_from_switch(key)
            if data_key :
                data_value = self.get_metadata_value_from_switch(value, key)
                self.set_metadata(data_key, data_value)
    
    def get_metadata_key_from_switch (self, switch) :
        key = None
        key_map = self.get_switch_to_metadata_mapping()
        if key_map.get(switch) :
            key = key_map.get(switch)
        return key
            
    def get_metadata_value_from_switch (self, value, switch) :
        return value
    
    def get_switch_to_metadata_mapping (self) :
        return {
            "local": "Packaged In",
            "remote": "Staged To",
            "au_file_size": "File Size",
            "au_title": "AU Package",
            "au_notes": "AU Notes",
            "jar": "Plugin JAR",
            "directory": "Directory name",
            "subdirectory": "Directory name",
            "peer": "From Peer",
            "publisher": "From Peer"
        }
    
    @property
    def plugin_jar (self) :
        return self.metadata.get('Plugin JAR')
    
    @plugin_jar.setter
    def plugin_jar (self, rhs) :
        try :
            assert rhs is not None, "plugin_jar must not be None"
            parts = urllib.parse.urlparse(rhs)
            assert all([parts.scheme, parts.netloc]), "plugin_jar must have a scheme and a netloc"
            self.accept_metadata({ "Plugin JAR": rhs })
        except AttributeError as e :
            if type(rhs) != str :
                raise TypeError("plugin_jar must be set to a string containing a valid URL", rhs) from e
            else :
                raise
        except AssertionError as e :
            raise ValueError("plugin_jar must be set to a string containing a valid URL", rhs) from e
    
    @property
    def au_title (self) :
        return first_of( [ self.metadata.get(key) for key in [ "AU Package", "Ingest Title" ] ] )
    
    @au_title.setter
    def au_title (self, rhs: str) :
        self.set_metadata("AU Package", rhs)
        self.set_metadata("Ingest Title", rhs)
    
    @property
    def ingest_title (self) :
        return first_of( [ self.metadata.get(key) for key in [ "Ingest Title", "AU Package", "Directory name" ] ] )
    
    def regex_title_prefix (self, margin=r"[^A-Za-z0-9]+") :
        split = '[^A-Za-z0-9]+'
        return r"^\s*%(regex)s%(margin)s" % {
            "regex": split.join([ word.lower() for word in re.split(split, self.institution if self.institution is not None else '') ]),
            "margin": margin
        }
    
    def filter_au_package (self, title, depth=0) :
        if depth <= 1 :
            self.set_metadata("Ingest Title", title, depth=depth)
        au_title = title
        if self.institution is not None and au_title is not None :
            re.sub(self.regex_title_prefix(), "", au_title, flags=re.I)
        return au_title
        
    def filter_ingest_title (self, title, depth=0) :
        au_title = title
        if self.institution is not None and au_title is not None :
            if not re.match(self.regex_title_prefix(), au_title, re.I) :
                au_title = re.sub(r"^\s*", "%(institution)s: " % { "institution": self.institution }, au_title)
        return au_title
        
    @property
    def institution (self) :
        institution = self.switches.get("institution")
        if institution is None :
            institution = self.publisher_code
        return institution
    
    @property
    def publisher_code (self) :
        from_switches = [ self.switches.get(key) for key in [ "publisher", "peer" ] ]
        from_metadata = [ self.metadata.get(key) for key in [ "Publisher", "From Peer", "Peer" ] ]
        publisher = first_of( from_switches + from_metadata )
        return publisher.upper() if type(publisher) is str else publisher
    
    @property
    def institution_name_with_code (self) :
        institution_name = self.institution
        if ( self.publisher_code ) and ( self.publisher_code != self.institution ) :
            institution_name = ( "%(institution)s (%(code)s)" % {
                "institution": self.institution,
                "code": self.publisher_code
            } )
        return institution_name
    
    @property
    def staging_user (self) :
        pub_code = self.publisher_code.lower() if type(self.publisher_code) is str else None
        return first_of( [ self.switches.get('stage/user'), pub_code ] )
    
    @staging_user.setter
    def staging_user (self, rhs) :
        self.switches['stage/user'] = rhs
        
    @property
    def staging_subdirectory (self) :
        return first_of( [ self.switches.get(key) for key in [ "directory", "subdirectory" ] ] )
    
    @property
    def parameters (self) :
        return self._parameters
    
    @parameters.setter
    def parameters (self, rhs) :
        self._parameters = rhs

    def set_parameter (self, key, new_value) :
        self._parameters = [ [ cur_key, new_value if key==cur_key else old_value ] for (cur_key, old_value) in self._parameters ]
    
    def get_manifest_parameters (self) :
        params = {
            "institution": self.institution,
            "institution_name": self.institution_name_with_code,
            "institution_code": self.staging_user, # FIXME: extract as necessary
            "institution_publisher_code": self.publisher_code,
            "au_title": self.au_title,
            "au_directory": self.staging_subdirectory, # FIXME: extract as necessary
            "au_file_size": self.get_au_file_size(cached=True, computed=True),
            "au_notes": self.metadata.get("AU Notes"),
            "drop_server": self.switches.get('base_url'), # FIXME: shuffle off switches
            "lockss_plugin": self.metadata.get('Plugin JAR'),
            "display_format": "text/html"
        }
        return params
        
    @property
    def plugin (self) -> myLockssPlugin :
        return self._plugin
    
    def get_path (self, item=None, canonicalize=False) -> str :
        path = self.path
        if item is not None :
            path = os.path.join(path, item)
        return os.path.realpath(path) if canonicalize else path
    
    def get_single_file_size (self, file) :
        size = None
        try :
            stat_results = os.stat(file)
            size = stat_results.st_size if stat.S_ISREG(stat_results.st_mode) else None
        except FileNotFoundError as e :
            pass
        return size
        
    def get_step_file_count (self, step) :
        n_dirs = len(step[1])
        n_files = len(step[2])
        return n_dirs + n_files
    
    def get_step_file_size (self, step) :
        s_parent = step[0]
        a_dirs = step[1]
        a_files = step[2]
        a_sizes = [ self.get_single_file_size(os.path.join(s_parent, s_file)) for s_file in a_files ]
        return sum(a_sizes)
    
    def get_file_size_human_readable (self, n_bytes, maximum="TiB") :
        orders = { "B": 1, "KiB": 1024, "MiB": 1024*1024, "GiB": 1024*1024*1024, "TiB": 1024*1024*1024*1024 }
        magnitude = n_bytes*1.0
        order = "B"
        stopped = False
        for ( unit, factor ) in orders.items() :
            if not stopped :
                if ( ( n_bytes*1.0 ) / ( factor*1.0) ) >= 1.0 :
                    magnitude = ( ( n_bytes*1.0 ) / ( factor*1.0) )
                    order = unit
            stopped = ( stopped or unit == maximum )
            
        return ( magnitude, order )
    
    @property
    def au_file_size (self) :
        return self.get_au_file_size(cached=True, computed=True)
    
    def get_au_file_size (self, cached=False, computed=True, start=None) :
        au_file_size = None
        if cached :
            au_file_size = self.metadata.get('File Size')
        if computed and ( au_file_size is None ) :
            node = self.get_path(start)
            items = os.listdir(node)
            walking_path = os.walk(node)
            levels = [ { "count": self.get_step_file_count(step), "size": self.get_step_file_size(step) } for step in walking_path ]
            
            extent = { "files": sum([ level["count"] for level in levels ]), "bytes": sum([ level["size"] for level in levels ]) }

            ( extent["size"], extent["unit"] ) = self.get_file_size_human_readable(extent["bytes"])
            extent["bplural"] = ( "s" if extent["bytes"] != 1 else "" )
            extent["fplural"] = ( "s" if extent["files"] != 1 else "" )
            extent["bytes"] = "{:,}".format(extent["bytes"])
        
            au_file_size = "%(size).1f %(unit)s (%(bytes)s byte%(bplural)s, %(files)s file%(fplural)s)" % extent
        return au_file_size
    
    def reset_au_file_size (self) :
        self.set_metadata("File Size", self.get_au_file_size())
        return self.metadata.get("File Size")
    
    def accept_bagit_results (self, exitcode, buf) :
        self._bagit_exitcode = exitcode
        self._bagit_output = re.split("[\r\n]+", buf) if buf is not None else None
    
    def has_bagit_enclosure (self) -> bool :
        has_it = False
        try :
            stat_results = os.stat(self.get_path("data"))
            has_data = stat.S_ISDIR(stat_results.st_mode)
            stat_results = os.stat(self.get_path("bagit.txt"))
            has_bagit = stat.S_ISREG(stat_results.st_mode)
            has_it = ( has_data and has_bagit )
        except FileNotFoundError as e :
            has_it = False
            pass
        return has_it
    
    def check_bagit_validation (self, halt=False) -> bool :
        
        buf = None
        if self.has_bagit_enclosure() :
            exitcode=0
            try :
                cmd = [ "python3", scripts.path("externals/bagit-python/bagit.py"), "--validate", self.get_path() ]
                buf = subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding="utf-8")
                self.accept_bagit_results(exitcode, buf)
            except subprocess.CalledProcessError as e :
                (exitcode, buf) = (e.returncode, e.output)
                self.accept_bagit_results(exitcode, buf)
                if halt :
                    raise AssertionError("BagIt", "BagIt validation process FAILED", self.get_path(), self._bagit_exitcode, self._bagit_output) from e
        elif halt :
            exitcode=256
            self.accept_bagit_results(exitcode, buf)
            raise AssertionError("BagIt", "BagIt formatting not found", self.get_path(), exitcode, "")
        else :
           exitcode=256

        return ( 0 == exitcode ) # 0=OK, non-0 = error code
    
    def make_bagit_enclosure (self, halt=False, validate=True) :
        exitcode = 0 if self.has_bagit_enclosure() else 256
        buf = None
        if 0 == exitcode :
            if validate :
                validates = self.check_bagit_validation(halt=halt)
                exitcode = ( 0 if validates else self._bagit_exitcode )
            else :
                self.accept_bagit_results(exitcode, buf)
        else :
            try :
                cmd = [ "python3", scripts.path("externals/bagit-python/bagit.py"), self.get_path() ]
                exitcode = 0
                buf = subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding="utf-8")
                self.accept_bagit_results(exitcode, buf)
            except subprocess.CalledProcessError as e :
                (exitcode, buf) = (e.returncode, e.output)
                self.accept_bagit_results(exitcode, buf)
                if halt :
                    raise AssertionError("BagIt formatting process FAILED", self.get_path(), self._bagit_exitcode, self._bagit_output) from e

        return self._bagit_output if ( 0 == exitcode ) else None # 0=OK, non-0 = error code
    
    def get_manifest (self) :
        manifest = None
        try :
            manifest_filename = self.get_path(self.plugin.get_manifest_filename(path=self.path))
            stat_results = os.stat(manifest_filename)
            manifest = [ manifest_filename, stat_results.st_size ] if stat.S_ISREG(stat_results.st_mode) else None
        except FileNotFoundError as e :
            pass
        return manifest
        
    def has_manifest (self) -> bool :
        return ( self.get_manifest() is not None )
    
    def check_manifest (self) :
        manifest = self.get_manifest()
        phrase = "LOCKSS system has permission to collect, preserve, and serve this Archival Unit"
        
        if manifest is None :
            raise AssertionError("manifest", "Manifest HTML does not exist", self.plugin.get_manifest_filename(path=self.path), phrase)

        # Check for the permission-to-harvest phrase
        html = ''.join(fileinput.input(files=manifest[0]))
        
        words = re.split(r'\s+', phrase)
        pattern = re.compile('\s+'.join(words), re.MULTILINE)
        m = re.search(pattern, html)
            
        if not m :
            raise AssertionError("manifest", "Manifest HTML exists, but does not contain permissions boilerplate language", self.plugin.get_manifest_filename(path=self.path), phrase)
    
    def read_manifest_data (self, overwrite=False, cascade=False) :
        manifest = self.get_manifest()
        
        # Check for JSON hash table embedded within manifest HTML
        table = {}
        if manifest is not None :
            try :
                html = [ line for line in fileinput.input(files=manifest[0]) ]
                jsonInput = myPyJSON()
                jsonInput.accept( html )
                table = jsonInput.allData
                
            except json.decoder.JSONDecodeError as e :
                # This might be the full text of a report. Can we find the JSON PACKET:
                # envelope nestled within it and strip out the other stuff?
                jsonInput.accept( html, screen=True ) 
                table = jsonInput.allData
                
        if table : 
            if overwrite :
                if cascade :
                    self.metadata.accept_metadata(table)
                else :
                    self.metadata = table
        
        return table

    def has_valid_manifest (self) :
        try :
            self.check_manifest()
            ok = True
        except AssertionError as e :
            if e.args[0] == 'manifest' :
                ok = False
            else :
                raise
        return ok
        
    def make_manifest (self) :
        return self.plugin.new_manifest(self.path, self.get_manifest_parameters())
