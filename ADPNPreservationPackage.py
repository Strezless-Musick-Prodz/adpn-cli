#!/usr/bin/python3
#
# ADPNPreservationPackage.py: provide the ADPNPreservationPackage class, an encapsulation of
# some operations dealing with packaging directories of files into AUs for ADPNet
#
# @version 2021.0629

import io, os, sys, stat
import subprocess
import json, re
import urllib
from myLockssScripts import myADPNScriptSuite

scripts = myADPNScriptSuite(__file__)

class myLockssPlugin :
    
    def __init__ (self, jar, parameters=None, switches=None) :
        self._parameters = ( parameters if parameters is not None else {} )
        self._switches = ( switches if switches is not None else {} )
        self._switches = { **{ "local": None, "proxy": None, "port": None, "tunnel": None, "tunnel-port": None }, **self._switches }
        self._jar = jar
    
    @property
    def jar (self) :
        return self._jar
    
    @property
    def switches (self) :
        return self._switches
    
    @property
    def parameters (self) :
        return self._parameters
    
    def get_manifest_filename (self) :
        filename = "manifestpage.html"

        try :
            jsonParams = json.dumps(self.parameters)
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
    
    def __init__ (self, path, parameters, switches) :
        self._path = path
        self._parameters = parameters
        self._switches = switches
        self._plugin = myLockssPlugin(jar=self.switches["jar"], parameters=parameters, switches=self.switches)
    
    @property
    def path (self) :
        return self._path
        
    @property
    def parameters (self) :
        return self._parameters
    
    @property
    def switches (self) -> dict :
        return self._switches
    
    @property
    def plugin (self) -> myLockssPlugin :
        return self._plugin
    
    def get_path (self, item=None) -> str :
        path = self.path
        if item is not None :
            path = os.path.join(path, item)
        return path
    
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
    
    def check_bagit_validation (self) -> bool :
        exitcode = 0 if self.has_bagit_enclosure() else 256
        buf = None
        if 0 == exitcode :
            try :
                cmdline = [
                    "python3",
                    scripts.path("externals/bagit-python/bagit.py"),
                        "--validate",
                        self.get_path()
                ]
                
                buf = subprocess.check_output(cmdline, stderr=subprocess.STDOUT, encoding="utf-8")
            except subprocess.CalledProcessError as e :
                exitcode = e.returncode
                buf = e.output
                
        self._bagit_exitcode = exitcode
        self._bagit_output = re.split("[\r\n]+", buf) if buf is not None else None
        return ( 0 == exitcode ) # 0=OK, non-0 = error code
    
    def make_bagit_enclosure (self) :
        exitcode = 0 if self.has_bagit_enclosure() else 256
        buf = None
        if 0 == exitcode :
            
            validates = self.check_bagit_validation()
            if not validates :
                raise OSError(package._bagit_exitcode, "BagIt validation FAILED", os.path.realpath(self.get_path()), self._bagit_output)
            
        else :
            
            try :
                cmdline = [
                    "python3",
                    scripts.path("externals/bagit-python/bagit.py"),
                        self.get_path()
                ]
                exitcode = 0
                buf = subprocess.check_output(cmdline, stderr=subprocess.STDOUT, encoding="utf-8")
            except subprocess.CalledProcessError as e :
                self._bagit_exitcode = e.returncode
                self._bagit_output = re.split("[\r\n]+", e.output)
                raise
        
            self._bagit_exitcode = exitcode
            self._bagit_output = re.split("[\r\n]+", buf) if buf is not None else None

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
    
    def make_manifest (self) :
        try :
            jsonParams = json.dumps(self.parameters)
            cmdline = [
                scripts.path("adpn-make-manifest.py"),
                    "--jar="+self.switches['jar'],
                    "--parameters="+jsonParams,
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

