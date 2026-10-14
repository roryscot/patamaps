    def _write_gzip_header(self, compresslevel):
        self.fileobj.write(b'\037\213')             # magic header
        self.fileobj.write(b'\010')                 # compression method
        try:
            # RFC 1952 requires the FNAME field to be Latin-1. Do not
            # include filenames that cannot be represented that way.
            fname = os.path.basename(self.name)
            if not isinstance(fname, bytes):
                fname = fname.encode('latin-1')
            if fname.endswith(b'.gz'):
                fname = fname[:-3]
        except UnicodeEncodeError:
            fname = b''
        flags = 0
        if fname:
            flags = FNAME
        self.fileobj.write(chr(flags).encode('latin-1'))
        mtime = self._write_mtime
        if mtime is None:
            mtime = time.time()
        write32u(self.fileobj, int(mtime))
        if compresslevel == _COMPRESS_LEVEL_BEST:
            xfl = b'\002'
        elif compresslevel == _COMPRESS_LEVEL_FAST:
            xfl = b'\004'
        else:
            xfl = b'\000'
        self.fileobj.write(xfl)
        self.fileobj.write(b'\377')
        if fname:
            self.fileobj.write(fname + b'\000')
