#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 Pawel Szostek (pawel.szostek@cern.ch)
#
#    This source code is free software; you can redistribute it
#    and/or modify it in source code form under the terms of the GNU
#    General Public License as published by the Free Software
#    Foundation; either version 2 of the License, or (at your option)
#    any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA
#

import os
import msg as p
import path

class ModulePool(list):
    class ModuleFetcher:
        def __init__(self):
            pass

        def fetch_single_module(self, module):
            new_modules = []
            p.vprint("Fetching module: " + str(module))

            if module.source == "local":
                p.vprint("ModPath: " + module.path);
            if module.source == "svn":
                p.vprint("[svn] Fetching to " + module.fetchto)
                self.__fetch_from_svn(module)
            if module.source == "git":
                p.vprint("[git] Fetching to " + module.fetchto)
                self.__fetch_from_git(module)

            module.parse_manifest()

#            if module.root_module != None:
#                p.vprint("Encountered root manifest: " + str(module.root_module))
#                new_modules.append(module.root_module)

            new_modules.extend(module.local)
            new_modules.extend(module.svn)
            new_modules.extend(module.git)
            return new_modules 

        def __fetch_from_svn(self, module):
            if not os.path.exists(module.fetchto):
                os.mkdir(module.fetchto)

            cur_dir = os.getcwd()
            os.chdir(module.fetchto)
            url, rev = self.__parse_repo_url(module.url)

            basename = path.svn_basename(url)

            cmd = "svn checkout {0} " + basename
            if rev:
                cmd = cmd.format(url + '@' + rev)
            else:
                cmd = cmd.format(url)

            rval = True

            p.vprint(cmd)
            if os.system(cmd) != 0:
                rval = False
            os.chdir(cur_dir)

            module.isfetched = True
            module.revision = rev
            module.path = os.path.join(module.fetchto, basename)
            return rval

        def __fetch_from_git(self, module):
            if not os.path.exists(module.fetchto):
                os.mkdir(module.fetchto)

            cur_dir = os.getcwd()
            url, rev = self.__parse_repo_url(module.url)

            basename = path.url_basename(url)

            if basename.endswith(".git"):
                basename = basename[:-4] #remove trailing .git

            if module.isfetched:
                update_only = True
            else:
                update_only = False

            if update_only:
                cmd = "git --git-dir="+os.path.join(module.fetchto, basename)+"/.git pull"
            else:
                os.chdir(module.fetchto)
                cmd = "git clone " + url

            rval = True

            p.vprint(cmd)
            if os.system(cmd) != 0:
                rval = False

            os.chdir(cur_dir)

            if rev and rval:
                os.chdir(os.path.join(module.fetchto, basename))
                cmd = "git checkout " + rev
                p.vprint(cmd)
                if os.system(cmd) != 0:
                    rval = False
                os.chdir(cur_dir)

            module.isfetched = True
            module.revision = rev
            module.path = os.path.join(module.fetchto, basename)
            return rval

        def __parse_repo_url(self, url) :
            """
            Check if link to a repo seems to be correct. Filter revision number
            """
            import re
            url_pat = re.compile("[ \t]*([^ \t]+)[ \t]*(@[ \t]*(.+))?[ \t]*")
            url_match = re.match(url_pat, url)

            if url_match == None:
                p.echo("Not a correct repo url: {0}. Skipping".format(url))
            if url_match.group(3) != None: #there is a revision given 
                ret = (url_match.group(1), url_match.group(3))
            else:
                ret = (url_match.group(1), None)
            return ret

    #end class ModuleFetcher
    def __init__(self):
        self.top_module = None 
        self.modules = []

    def get_fetchable_modules(self):
        return [m for m in self.modules if m.source != "local"]

    def __iter__(self):
        return self.modules.__iter__()

    def __len__(self):
        return len(self.modules)

    def __contains__(self,v):
        return v in self.modules

    def __getitem__(self,v):
        return self.modules[v]

    def __str__(self):
        return str([str(m) for m in self.modules])

    def __contains(self, module):
        for mod in self.modules:
            if mod.url == module.url:
                return True
        return False

    def set_top_module(self, module):
        self.top_module = module
        self.add(module)
        
    def Module(self, parent, url, source, fetchto):
        from module import Module
        if url in [m.url for m in self.modules]:
            return [m for m in self.modules if m.url == url][0]
        else:
            new_module = Module(parent=parent, url=url, source=source, fetchto=fetchto, pool=self)
            self.add(new_module)
            return new_module

    def add(self, new_module):
        from module import Module
        if not isinstance(new_module, Module):
            raise RuntimeError("Expecting a Module instance")
        if self.__contains(new_module):
            return
        if new_module.isfetched:
            for mod in new_module.submodules():
                self.add(mod)
        self.modules.append(new_module)
        return True

    def fetch_all(self):
        fetcher = self.ModuleFetcher()
        from copy import copy
        fetch_queue = copy(self.modules)

        while len(fetch_queue) > 0:
            cur_mod = fetch_queue.pop()
            new_modules = fetcher.fetch_single_module(cur_mod)

            for mod in new_modules:
                if not self.__contains(mod):
                    self.add(mod)
                    fetch_queue.append(mod)
                else:
                    pass

    def build_global_file_list(self):
        from srcfile import SourceFileSet
        ret = SourceFileSet()
        for m in self.modules:
            ret.add(m.files)
        return ret

    def build_very_global_file_list(self):
        from srcfile import SourceFileFactory, VerilogFile
        sff = SourceFileFactory()

        files = self.build_global_file_list()
        extra_verilog_files = set() 
        manifest_verilog_files = files.filter(VerilogFile)
        queue = manifest_verilog_files

        while len(queue) > 0:
            vl = queue.pop()
            for f in vl.dep_requires:
                nvl = sff.new(os.path.join(vl.dirname, f))
                queue.append(nvl)
                if f not in extra_verilog_files and f not in manifest_verilog_files:
                    extra_verilog_files.add(nvl)

        p.vprint("Extra verilog files, not listed in manifests:")
        for file in extra_verilog_files:
            p.vprint(str(file))
        for file in extra_verilog_files:
            files.add(file)
        return files

    def get_top_module(self):
        return self.top_module

    def is_everything_fetched(self):
        #for mod in self.modules:
        #    if mod.is_fetched_recursively() == False:
        #        return False
        #return True
        if len([m for m in self.modules if not m.isfetched]) == 0:
            return True
        else:
            return False
