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
from myLockssScripts import myADPNScriptSuite

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
            params = [ (key, value) for (key, value) in self.parameters ]
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
        
    def get_manifest_filename (self) :
        filename = "manifest.html"

        try :
            cmdline = [
                scripts.path("adpn-make-manifest.py"),
                    "--jar="+self.jar,
                    ( "--local=%(local)s" % self.switches ),
                    "--dry-run"
            ]
            if ( 'proxy' in self.switches.keys() ) and ( self.switches['proxy'] is not None ) :
                cmdline.append("--proxy="+self.switches['proxy'])
            if ( 'port' in self.switches.keys() ) and ( self.switches['port'] is not None ) :
                cmdline.append("--port="+self.switches['port'])
            if ( 'tunnel' in self.switches.keys() ) and ( self.switches['tunnel'] is not None ) :
                cmdline.append("--tunnel="+self.switches['tunnel'])
            if ( 'tunnel-port' in self.switches.keys() ) and ( self.switches['tunnel-port'] is not None ) :
                cmdline.append( "--tunnel-port="+self.switches['tunnel-port'])
            
            code = 0
            buf = subprocess.check_output(cmdline, encoding="utf-8")
        except subprocess.CalledProcessError as e :
            code = e.returncode
            buf = e.output
        
        if 0 == code : # OK!
            tsv = [ line.split("\t") for line in re.split("[\r\n]+", buf) ]
            filenames = [ os.path.basename(row[0]) for row in tsv ]
            filename = ( filenames[0] if len(filenames) > 0 else filename )
            
        return filename
    
class ADPNPreservationPackage :
    
    def __init__ (self, path, plugin_parameters, manifest_parameters, switches) :
        self._path = path
        self._parameters = plugin_parameters
        self._manifest = manifest_parameters
        self._switches = switches
        self._plugin = myLockssPlugin(jar=self.switches["jar"], parameters=plugin_parameters, switches=self.switches)
        
    @property
    def path (self) :
        return self._path
        
    @property
    def parameters (self) :
        return self._parameters
    
    @parameters.setter
    def parameters (self, rhs) :
        self._parameters = rhs

    def set_parameter (self, key, new_value) :
        self._parameters = [ [ cur_key, new_value if key==cur_key else old_value ] for (cur_key, old_value) in self._parameters ]

    @property
    def manifest (self) :
        return self._manifest
    
    @manifest.setter
    def manifest (self, rhs) :
        self._manifest = rhs
        
    def set_manifest (self, key, value) :
        self._manifest[key] = value
        
    @property
    def switches (self) -> dict :
        return self._switches
    
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
        
    def get_au_file_size (self, start=None) :
        node = self.get_path(start)
        items = os.listdir(node)
        walking_path = os.walk(node)
        levels = [ { "count": self.get_step_file_count(step), "size": self.get_step_file_size(step) } for step in walking_path ]
        
        extent = { "files": sum([ level["count"] for level in levels ]), "bytes": sum([ level["size"] for level in levels ]) }

        ( extent["size"], extent["unit"] ) = self.get_file_size_human_readable(extent["bytes"])
        extent["bplural"] = ( "s" if extent["bytes"] != 1 else "" )
        extent["fplural"] = ( "s" if extent["files"] != 1 else "" )
        extent["bytes"] = "{:,}".format(extent["bytes"])
        
        return "%(size).1f %(unit)s (%(bytes)s byte%(bplural)s, %(files)s file%(fplural)s)" % extent
    
    def reset_au_file_size (self) :
        self.set_manifest("au_file_size", self.get_au_file_size())
        return self.manifest.get("au_file_size")
    
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
            manifest_filename = self.get_path(self.plugin.get_manifest_filename())
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
            raise AssertionError("manifest", "Manifest HTML does not exist", self.plugin.get_manifest_filename(), phrase)

        # Check for the permission-to-harvest phrase
        html = ''.join(fileinput.input(files=manifest[0]))
        
        words = re.split(r'\s+', phrase)
        pattern = re.compile('\s+'.join(words), re.MULTILINE)
        m = re.search(pattern, html)
            
        if not m :
            raise AssertionError("manifest", "Manifest HTML exists, but does not contain permissions boilerplate language", self.plugin.get_manifest_filename(), phrase)
    
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
        try :
            jsonManifestParams = json.dumps(self.manifest)
            cmdline = [
                scripts.path("adpn-make-manifest.py"),
                    "--jar="+self.switches['jar'],
                    "--parameters="+jsonManifestParams,
                    "--local="+self.switches['local']
            ]
            if ( 'proxy' in self.switches.keys() ) and ( self.switches['proxy'] is not None ) :
                cmdline.append("--proxy="+self.switches['proxy'])
            if ( 'port' in self.switches.keys() ) and ( self.switches['port'] is not None ) :
                cmdline.append("--port="+self.switches['port'])
            if ( 'tunnel' in self.switches.keys() ) and ( self.switches['tunnel'] is not None ) :
                cmdline.append("--tunnel="+self.switches['tunnel'])
            if ( 'tunnel-port' in self.switches.keys() ) and ( self.switches['tunnel-port'] is not None ) :
                cmdline.append( "--tunnel-port="+self.switches['tunnel-port'])
            
            buf = subprocess.check_output(cmdline, encoding="utf-8")
        except subprocess.CalledProcessError as e :
            code = e.returncode
            buf = e.output
        
        return buf

