# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 Pawel Szostek (pawel.szostek@cern.ch)
#
#    This source code is free software; you can redistribute it
#    and/or modify it in source code form under the terms of the GNU
#    General Public License as published by the Free Software
#    Foundation; either  2 of the License, or (at your option)
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

import path as path_mod
import msg as p
import os
import global_mod
from helper_classes import Manifest, ManifestParser
from srcfile import SourceFileSet, SourceFileFactory 

class Module(object):
    @property
    def source(self):
        return self._source
    @source.setter
    def source(self, value):
        if value not in ["svn","git","local"]:
            raise ValueError("Inproper source: " + value)
        self._source = value
    @source.deleter
    def source(self):
        del self._source
###
    @property
    def basename(self):
        import path
        if self.source == "svn":
            return path.svn_basename(self.url)
        else:
            return path.url_basename(self.url)

    def __init__(self, parent, url, source, fetchto, pool):
        #self.options = ManifestOptions()
        self.fetchto = fetchto
        self.pool = pool
        self.source = source
        self.parent = parent
        self.isparsed = False
        self.library = "work"
        self.local = []
        self.git = []
        self.svn = []
        self.ise = []
        self.target = None
        self.action = None
        self.vmap_opt = None
        self.vlog_opt = None
        self.vcom_opt = None
        self.revision = None
        self._files = None
        self.manifest = None
        self.url = url

        if source == "local" and not os.path.exists(url):
            p.rawprint("Path to the local module doesn't exist:\n" + url)
            p.rawprint("This module was instantiated in: " + str(parent))

        if source == "local":
            self.path = url
            self.isfetched = True
        else:
            if os.path.exists(os.path.join(fetchto, self.basename)):
                self.path = os.path.join(fetchto, self.basename)
                self.isfetched = True
            else:
                self.path = None
                self.isfetched = False

        if self.path != None:
            self.manifest = self.__search_for_manifest()
        else:
            self.manifest = None

    def __str__(self):
        return self.url

    @property
    def is_fetched_to(self):
        return os.path.dirname(self.path)

    def submodules(self):
        def __nonull(x):
            if not x:
                return []
            else:
                return x

        return __nonull(self.local) + __nonull(self.git) + __nonull(self.svn)

    def __search_for_manifest(self):
        """
        Look for manifest in the given folder
        """
        p.vprint("Looking for manifest in " + self.path)
        for filename in os.listdir(self.path):
            if filename == "manifest.py" or filename == "Manifest.py":
                if not os.path.isdir(filename):
                    p.vprint("*** found manifest for module "+self.path);
                    manifest = Manifest(path=os.path.abspath(os.path.join(self.path, filename)))
                    return manifest
        return None

    def __make_list(self, sth):
        if sth != None:
            if not isinstance(sth, (list,tuple)):
                sth = [sth]
        else:
            sth = []
        return sth

    def parse_manifest(self):
        if self.isparsed == True or self.isfetched == False:
            return
        if self.manifest == None:
            self.manifest = self.__search_for_manifest()
        if self.path == None:
            raise RuntimeError()
        manifest_parser = ManifestParser()

        if(self.parent != None):
            manifest_parser.add_arbitrary_code("target=\""+str(global_mod.top_module.target)+"\"")
            manifest_parser.add_arbitrary_code("action=\""+str(global_mod.top_module.action)+"\"")

        manifest_parser.add_arbitrary_code("__manifest=\""+self.url+"\"")
        manifest_parser.add_arbitrary_code(global_mod.options.arbitrary_code)

        if self.manifest == None:
            p.vprint("No manifest found in module "+str(self))
        else:
            manifest_parser.add_manifest(self.manifest)
            p.vprint("Parsing manifest file: " + str(self.manifest))

        opt_map = None
        try:
            opt_map = manifest_parser.parse()
        except NameError as ne:
            p.echo("Error while parsing {0}:\n{1}: {2}.".format(self.manifest, type(ne), ne))
            quit()
       #if opt_map["root_module"] != None:
       #     root_path = path_mod.rel2abs(opt_map["root_module"], self.path)
       #     self.root_module = Module(path=root_path, source="local", isfetched=True, parent=self)
       #     self.root_module.parse_manifest()


        if(opt_map["fetchto"] != None):
            fetchto = path_mod.rel2abs(opt_map["fetchto"], self.path)
            self.fetchto = fetchto
        else:
            fetchto = self.fetchto

        if self.ise == None:
            self.ise = "13.1"

        if "local" in opt_map["modules"]:
            local_paths = self.__make_list(opt_map["modules"]["local"])
            local_mods = []
            for path in local_paths:
                if path_mod.is_abs_path(path):
                    p.echo("Found an absolute path (" + path + ") in a manifest")
                    p.echo("(" + self.path + ")")
                    quit()
                path = path_mod.rel2abs(path, self.path)
                local_mods.append(self.pool.Module(parent=self, url=path, source="local", fetchto=fetchto))
            self.local = local_mods
        else:
            self.local = []

        self.vmap_opt = opt_map["vmap_opt"]
        self.vcom_opt = opt_map["vcom_opt"]
        self.vsim_opt = opt_map["vsim_opt"]
        self.vlog_opt = opt_map["vlog_opt"]
        if self.vlog_opt == None:
            self.vlog_opt = global_mod.top_mod.vlog_opt
        self.library = opt_map["library"]

        if opt_map["files"] == []:
            self.files = SourceFileSet()
        else:
            opt_map["files"] = self.__make_list(opt_map["files"])
            paths = []
            for path in opt_map["files"]:
                if path_mod.is_abs_path(path):
                    p.echo(path + " is an absolute path. Omitting.")

                path = path_mod.rel2abs(path, self.path)
                if not os.path.exists(path):
                    p.echo("File listed in " + self.manifest.path + " doesn't exist: "
                    + path +".\nExiting.")
                    quit()

                if os.path.isdir(path):
                    for f in os.listdir(path):
                        tmp_path = path_mod.rel2abs(os.path.join(path, f), self.path)
                        if not os.path.isdir(tmp_path):
                            paths.append(tmp_path)
                
                else:
                    paths.append(path)

            self.files = self.__create_flat_file_list(paths=paths);
            for f in self.files:
                f.vlog_opt = self.vlog_opt

        if "svn" in opt_map["modules"]:
            opt_map["modules"]["svn"] = self.__make_list(opt_map["modules"]["svn"])
            svn_mods = []
            for url in opt_map["modules"]["svn"]:
                svn_mods.append(self.pool.Module(parent=self, url=url, source="svn", fetchto=fetchto))
            self.svn = svn_mods
        else:
            self.svn = []

        if "git" in opt_map["modules"]:
            opt_map["modules"]["git"] = self.__make_list(opt_map["modules"]["git"])
            git_mods = []
            for url in opt_map["modules"]["git"]:
                git_mods.append(self.pool.Module(parent=self, url=url, source="git", fetchto=fetchto))
            self.git = git_mods
        else:
            self.git = []

        self.target = opt_map["target"]
        self.action = opt_map["action"]



        if opt_map["syn_name"] == None and opt_map["syn_project"] != None:
            self.syn_name = opt_map["syn_project"][:-5] #cut out .xise from the end
        else:
            self.syn_name = opt_map["syn_name"]
        self.syn_device = opt_map["syn_device"];
        self.syn_grade = opt_map["syn_grade"];
        self.syn_package= opt_map["syn_package"];
        self.syn_project = opt_map["syn_project"];
        self.syn_top = opt_map["syn_top"];
        
        sff = SourceFileFactory()
        self.syn_preflow = self.syn_postflow = None
        if opt_map["syn_preflow"]:
            self.syn_preflow = sff.new(opt_map["syn_preflow"])
        if opt_map["syn_postflow"]:
            self.syn_postflow = sff.new(opt_map["syn_postflow"])

        self.isparsed = True

        for m in self.submodules():
            m.parse_manifest()

    def is_fetched_recursively(self):
        if not self.isfetched:
            return False
        for mod in self.submodules():
            if mod.is_fetched_recursively() == False:
                return False
        return True

    def make_list_of_modules(self):
        p.vprint("Making list of modules for " + str(self))
        new_modules = [self]
        modules = [self]
        while len(new_modules) > 0:
            cur_module = new_modules.pop()
            if not cur_module.isfetched:
                p.echo("Error in modules list - unfetched module: " + str(cur_module))
                quit()
            if cur_module.manifest == None:
                p.vprint("No manifest in " + str(cur_module))
                continue
            cur_module.parse_manifest()
#            if cur_module.root_module != None:
#                root_module = cur_module.root_module
#                modules_from_root = root_module.make_list_of_modules()
#                modules.extend(modules_from_root)

            for module in cur_module.local:
                modules.append(module)
                new_modules.append(module)

            for module in cur_module.git:
                modules.append(module)
                new_modules.append(module)

            for module in cur_module.svn:
                modules.append(module)
                new_modules.append(module)

        if len(modules) == 0:
            p.vprint("No modules were found in " + self.fetchto)
        return modules


    def __create_flat_file_list(self, paths):
        sff = SourceFileFactory()
        srcs = SourceFileSet()
        for p in paths:
            if os.path.isdir(p):
                dir = os.listdir(p)
                for f_dir in dir:
                    f_dir = os.path.join(self.path, p, f_dir)
                    if not os.path.isdir(f_dir):
                        srcs.add(sff.new(f_dir))
            else:
                srcs.add(sff.new(p, self.library))
        return srcs

    def build_global_file_list(self):
        f_set = SourceFileSet()
#        self.create_flat_file_list();
        modules = self.make_list_of_modules()
        for m in modules:
            f_set.add(m.files);

        return f_set
