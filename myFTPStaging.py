#!/usr/bin/python3
#
# myFTPStaging.py: provide the myFTPStaging class, a gateway to upload and download files from a file server
# using either FTP (via Python ftplib) or SFTP (via pysftp) client classes
#
# @version 2021.0629

import io, os, sys, errno, re
import ftplib, pysftp
from io import BytesIO
from ftplib import FTP

class myFTPStaging :

    def __init__ (self, ftp, user, host, dry_run=False) :
        self.ftp = ftp
        self.user = user
        self.host = host
        self.dry_run = dry_run
        
    def is_sftp (self) :
        return isinstance(self.ftp, pysftp.Connection)
    
    def is_ftp (self) :
        return isinstance(self.ftp, FTP)
    
    def get_protocol (self) :
        return "sftp" if self.is_sftp() else "ftp"
    
    def get_file_size (self, file) :
        size=None
        try :
            if self.is_sftp() :
                stat=self.ftp.stat(file)
                size=stat.st_size
            else :
                size=self.ftp.size(file)
        except FileNotFoundError :
            pass
        except ftplib.error_perm :
            pass
        
        return size
    
    def is_directory (self, file) :
        if self.is_sftp() :
            test_directory = self.ftp.isdir(file)
        else :
            test_directory = ( '.' == file or self.get_file_size(file) is None )
        return test_directory
        
    def url_host (self) :
        return ("%(user)s@%(host)s" if self.user else "%(host)s") % {"user": self.user, "host": self.host}
    
    def url (self) :
        return "%(protocol)s://%(host)s%(path)s" % {"protocol": self.get_protocol(), "host": self.url_host(), "path": self.get_location(remote=True) }
    
    def get_location (self, remote=False, local=False) :
        remote_pwd = ( self.ftp.getcwd() if self.is_sftp() else self.ftp.pwd() )
        local_pwd = os.getcwd()
        
        if remote and local :
            result = ( local_pwd, remote_pwd )
        elif remote :
            result = ( remote_pwd )
        elif local :
            result = ( local_pwd )
        # Default to remote only...
        else :
            result = ( remote_pwd )
            
        return result
    
    def remove_item (self, file) :
        if self.dry_run :
            pass
        elif self.is_sftp() :
            self.ftp.remove(file)
        else :
            self.ftp.delete(file)
    
    def new_directoryitem (self, dir) :
        if self.dry_run :
            pass
        elif self.is_sftp() :
            self.ftp.mkdir(dir)
        else :
            self.ftp.mkd(dir)
    
    def remove_directoryitem (self, dir) :
        if self.dry_run :
            pass
        elif self.is_sftp() :
            self.ftp.rmdir(dir)
        else :
            self.ftp.rmd(dir)
    
    def set_location (self, dir=None, remote=None, make=False) :
        llast = self.get_location(local=True)
        try :
            if dir is not None :
                os.chdir(dir)
        except FileNotFoundError as e :
            if self.dry_run :
                pass
            elif make :
                os.mkdir(dir)
                os.chdir(dir)
            else :
                raise
        
        rdir = remote if remote is not None else dir
        rlast = self.set_remotelocation(dir=rdir, make=make)
        
        return (llast, rlast)
        
    def set_remotelocation (self, dir, make=False) :
        last = self.get_location(remote=True)
        
        exists = False
        try :
            if self.is_sftp() :
                self.ftp.chdir(dir)
                exists = True
            else :
                self.ftp.cwd(dir)
                exists = True
        except ftplib.error_perm as e :
            pass
        except FileNotFoundError as e :
            pass
        
        if not exists :
            
            if not self.dry_run and make :
                self.new_directoryitem(dir)
                self.set_remotelocation(dir, make=False)
            else :
                remote_file = "/".join([ self.url(), dir])
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), remote_file)
            
        return last
    
    def get_childitem (self) :
        return self.ftp.listdir() if self.is_sftp() else self.ftp.nlst()

    def download_file (self, file = None) :
        try :
            if self.dry_run :
                pass
            elif self.is_sftp() :
                self.ftp.get(file)
            else :
                self.ftp.retrbinary("RETR %(file)s" % {"file": file}, open( file, 'wb' ).write)
        except OSError :
            pass

    def download (self, file = None, exclude = None, notification = None) :
        out = notification if notification is not None else lambda level, type, arg: (level, type, arg) # NOOP
        
        if self.is_directory(file) :
            
            if '.' != file :
                
                (lpwd, rpwd) = self.set_location(dir=file, make=True)
                out(2, "chdir", self.get_location(local=True, remote=True))

            listing = [ item for item in self.get_childitem() ]
            listing.sort(key=lambda name: not re.match(r'^[Mm]anifest.*$', name))
            for subfile in listing :
                exclude_this = exclude(subfile) if exclude is not None else False
                if not exclude_this :
                    (level, type) = (1, "downloaded")
                    self.download(file=subfile, exclude=exclude, notification=notification)
                    
                else :
                    (level, type) = (2, "excluded")
                
                out(level, type, subfile)

            if '.' != file :

                self.set_location(dir=lpwd, remote=rpwd, make=False)
                out(2, "chdir", (lpwd, rpwd))
                self.remove_directoryitem(file)
                out(2, "remove_directoryitem", file)
        
        else :
            self.download_file(file=file)
            if not self.dry_run and self.get_file_size(file) == os.stat(file).st_size :
                self.remove_item(file)
                out(2, "remove_item", file)
    
    def upload_file (self, blob = None, file = None) :
        if isinstance(blob, str) :
            blob = blob.encode("utf-8")
        
        if self.dry_run :
            pass
        elif self.is_sftp() :
            if blob is not None :
                self.ftp.putfo(io.BytesIO(bytes(blob)), remotepath=file)
            else :
                self.ftp.put(file)
        else :
            stream=BytesIO(bytes(blob)) if blob is not None else open(file, 'rb')
            self.ftp.storbinary("STOR %(filename)s" % {"filename": file}, stream)
            stream.close()
    
    def upload (self, blob = None, file = None, exclude = None, notification = None) :
        out = notification if notification is not None else lambda level, type, arg: (level, type, arg) # NOOP
        
        if blob is not None :
            self.upload_file(blob, file)
        elif os.path.isfile(file) :
            self.upload_file(blob=None, file=file)
        elif '.' == file or os.path.isdir(file) :
            (lpwd, rpwd) = self.get_location(local=True, remote=True)
            if '.' != file :
                try :
                    (lpwd, rpwd) = self.set_location(dir=file, make=True)
                except FileNotFoundError as e :
                    if self.dry_run :
                        pass
                    else :
                        raise
                out(2, "chdir", self.get_location(local=True, remote=True))

            for subfile in os.listdir() :
                exclude_this = exclude(subfile) if exclude is not None else False
                if not exclude_this :
                    (level, type) = (1, "uploaded")
                    if self.get_file_size(subfile) != os.stat(subfile).st_size :
                        self.upload(blob=None, file=subfile, exclude=exclude, notification=notification)
                else :
                    (level, type) = (2, "excluded")
                    
                out(level, type, subfile)

            if '.' != file :
                out(2, "chdir", (lpwd, rpwd))
                self.set_location(dir=lpwd, remote=rpwd, make=False)
            
    def quit (self) :
        if self.is_sftp() :
            self.ftp.close()
        else :
            self.ftp.quit()

