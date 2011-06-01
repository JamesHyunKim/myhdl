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
from makefile_writer import MakefileWriter
from dep_solver import DependencySolver
from flow import ISEProject, QuartusProject
from srcfile import SourceFileFactory

class HdlmakeKernel(object):
    def __init__(self, modules_pool, connection):
        self.modules_pool = modules_pool
        self.connection = connection
        self.make_writer = MakefileWriter("Makefile")
        self.solver = DependencySolver()
        
    @property
    def top_module(self):
        return self.modules_pool.get_top_module()

    def run(self):
        tm = self.top_module

        if not self.modules_pool.is_everything_fetched():
            self.fetch()

        if tm.action == "simulation":
            self.generate_modelsim_makefile()
        elif tm.action == "synthesis":
            if tm.syn_project == None:
                p.rawprint("syn_project variable must be defined in the manfiest")
                p.quit()
            if tm.target.lower() == "xilinx":
                self.generate_ise_project()
                self.generate_ise_makefile()
                self.generate_ise_remote_synthesis_makefile()
            elif tm.target.lower() == "altera":
                self.generate_quartus_project()
                self.generate_quartus_makefile()
                self.generate_quartus_remote_synthesis_makefile()
            else:
                raise RuntimeError("Unrecognized target: "+tm.target)
        else:
            p.rawprint("Unrecognized action: " + str(tm.action))
            p.rawprint("Allowed actions are:\n\tsimulation\n\tsynthesis")
            quit()
        self.generate_fetch_makefile()

    def fetch(self):
        p.rawprint("Fetching needed modules...")
        self.modules_pool.fetch_all()
        p.vprint(str(self.modules_pool))

    def generate_modelsim_makefile(self):
        p.rawprint("Generating makefile for simulation...")

        self.__check_if_fetched()
        tm = self.modules_pool.get_top_module()
        flist = self.modules_pool.build_global_file_list()
        flist_sorted = self.solver.solve(flist)
        self.make_writer.generate_modelsim_makefile(flist_sorted, tm)

    def generate_ise_makefile(self):
        p.rawprint("Generating makefile for local synthesis...")
        ise = self.__check_ise_version()
        self.make_writer.generate_ise_makefile(top_mod=self.modules_pool.get_top_module(), ise=ise)

    def generate_quartus_makefile(self):
        p.rawprint("Generating makefile for local synthesis...")
        self.make_writer.generate_quartus_makefile(top_mod=self.modules_pool.get_top_module())

    def generate_quartus_remote_synthesis_makefile(self):
        if self.connection.ssh_user == None or self.connection.ssh_server == None:
            p.rawprint("Connection data is not given. Accessing environmental variables in the makefile")
        p.rawprint("Generating makefile for remote synthesis...")

        top_mod = self.modules_pool.get_top_module()
        files = self.modules_pool.build_very_global_file_list()

        sff = SourceFileFactory()
        files.add(sff.new(top_mod.syn_project))
        files.add(top_mod.syn_preflow)
        files.add(top_mod.syn_postflow)

        self.make_writer.generate_remote_synthesis_makefile(files=files, name=top_mod.syn_name, 
        cwd=os.getcwd(), user=self.connection.ssh_user, server=self.connection.ssh_server)
        
    def generate_ise_remote_synthesis_makefile(self):
        if self.connection.ssh_user == None or self.connection.ssh_server == None:
            p.rawprint("Connection data is not given. Accessing environmental variables in the makefile")
        p.rawprint("Generating makefile for remote synthesis...")

        top_mod = self.modules_pool.get_top_module()
        tcl = self.__search_tcl_file()
        ise = self.__check_ise_version()
        if tcl == None:
            self.__generate_tcl()
            tcl = "run.tcl"
        files = self.modules_pool.build_very_global_file_list()

        sff = SourceFileFactory()
        files.add(sff.new(tcl))
        files.add(sff.new(top_mod.syn_project))

        self.make_writer.generate_remote_synthesis_makefile(files=files, name=top_mod.syn_name, 
        cwd=os.getcwd(), user=self.connection.ssh_user, server=self.connection.ssh_server, ise=ise)

    def generate_quartus_project(self):
        p.rawprint("Generating/updating Quartus project...")
        self.__check_if_fetched()

        top_mod = self.modules_pool.get_top_module()
        files = top_mod.build_global_file_list()
        files = self.solver.solve(files)
        
        if os.path.exists(self.top_module.syn_project+'.qsf'):
            self.__update_existing_quartus_project(top=top_mod, files=files)
        else:
            self.__create_new_quartus_project(top=top_mod, files=files)

    def generate_ise_project(self):
        p.rawprint("Generating/updating ISE project...")
        self.__check_if_fetched()
        if self.__is_xilinx_screwed():
            p.rawprint("Xilinx environment variable is unset or is wrong.\nCannot generate ise project")
            quit()

        top_mod = self.modules_pool.get_top_module()
        files = top_mod.build_global_file_list()
        files = self.solver.solve(files)
        ise = self.__check_ise_version()

        if os.path.exists(self.top_module.syn_project):
            self.__update_existing_ise_project(ise=ise, top=top_mod, files=files)
        else:
           self.__create_new_ise_project(ise=ise, top=top_mod, files=files)

    def __check_if_fetched(self):
        if not self.modules_pool.is_everything_fetched():
            p.echo("A module remains unfetched. Fetching must be done prior to makefile generation")
            p.echo(str([str(m) for m in self.modules_pool.modules if not m.isfetched]))
            quit()

    def __is_xilinx_screwed(self):
        if self.__check_ise_version() == None:
            return True
        else:
            return False

    def __check_ise_version(self):
        xilinx = os.getenv("XILINX")
        if xilinx == None:
            return None
        else:
            import re
            vp = re.compile(".*?(\d\d\.\d).*")
            m = re.match(vp, xilinx)
            if m == None:
                return None
            return m.group(1)

    def __create_new_quartus_project(self, top, files):
        QPP = QuartusProject.QuartusProjectProperty
        prj = QuartusProject(top.syn_project)
        prj.add_files(files)

        prj.add_property(QPP(QPP.SET_GLOBAL_ASSIGNMENT, name_type='FAMILY', name=top.syn_device))
        prj.add_property(QPP(QPP.SET_GLOBAL_ASSIGNMENT, name_type='DEVICE', name='auto'))
        prj.add_property(QPP(QPP.SET_GLOBAL_ASSIGNMENT, name_type='TOP_LEVEL_ENTITY', name=top.syn_top))
        prj.preflow = top.syn_preflow
        prj.postflow = top.syn_postflow
        
        prj.emit()

    def __update_existing_quartus_project(self, top, files):
        print("update")
        prj = QuartusProject(top.syn_project)
        prj.read()
        prj.preflow = top.syn_preflow
        prj.postflow = top.syn_postflow
        prj.add_files(files)
        prj.emit()

    def __create_new_ise_project(self, ise, top, files):
        prj = ISEProject(ise=ise)
        ISEProjectProperty = ISEProject.ISEProjectProperty
        prj.add_files(files)
        prj.add_libs(files.get_libs())

        prj.add_property(ISEProjectProperty("Device", top.syn_device))
        prj.add_property(ISEProjectProperty("Device Family", "Spartan6"))
        prj.add_property(ISEProjectProperty("Speed Grade", top.syn_grade))
        prj.add_property(ISEProjectProperty("Package", top.syn_package))
        #    prj.add_property(ISEProjectProperty("Implementation Top", "Architecture|"+top.syn_top))
        prj.add_property(ISEProjectProperty("Enable Multi-Threading", "2"))
        prj.add_property(ISEProjectProperty("Enable Multi-Threading par", "4"))
        prj.add_property(ISEProjectProperty("Implementation Top", "Architecture|"+top.syn_top))
        prj.add_property(ISEProjectProperty("Manual Implementation Compile Order", "true"))
        prj.add_property(ISEProjectProperty("Auto Implementation Top", "false"))
        prj.add_property(ISEProjectProperty("Implementation Top Instance Path", "/"+top.syn_top))
        prj.emit_xml(top.syn_project)

    def __update_existing_ise_project(self, ise, top, files):
        prj = ISEProject(ise=ise)
        prj.add_files(files)
        prj.add_libs(files.get_libs())
        prj.load_xml(top.syn_project)
        prj.emit_xml(top.syn_project)

    def run_local_synthesis(self):
        tm = self.modules_pool.get_top_module()
        if tm.target == "xilinx":
            if not os.path.exists("run.tcl"):
                self.__generate_tcl()
            os.system("xtclsh run.tcl");
        else:
            p.echo("Target " + tm.target + " is not synthesizable")

    def run_remote_synthesis(self):
        ssh = self.connection
        tm = self.modules_pool.get_top_module()
        cwd = os.getcwd()

        p.vprint("The program will be using ssh connection: "+str(ssh))
        if not ssh.is_good():
            p.echo("SSH connection failure. Remote host doesn't response.")
            quit()

        if not os.path.exists(tm.fetchto):
            p.echo("There are no modules fetched. Are you sure it's correct?")

        files = self.modules_pool.build_very_global_file_list()
        tcl = self.__search_tcl_file()
        if tcl == None:
            tcl = self.__generate_tcl()

        sff = SourceFileFactory()
        files.add(sff.new(tcl))
        files.add(sff.new(tm.syn_project))

        dest_folder = ssh.transfer_files_forth(files, dest_folder=tm.syn_name)
        syn_cmd = "cd "+dest_folder+cwd+" && xtclsh run.tcl"

        p.vprint("Launching synthesis on " + str(ssh) + ": " + syn_cmd)
        ret = ssh.system(syn_cmd)
        if ret == 1:
            p.echo("Synthesis failed. Nothing will be transfered back")
            quit()

        cur_dir = os.path.basename(cwd)
        os.chdir("..")
        ssh.transfer_files_back(what=dest_folder+cwd, where=".")
        os.chdir(cur_dir)

    def __search_tcl_file(self, directory = None):
        if directory == None:
            directory = "."
        dir = os.listdir(directory)
        tcls = []
        for file in dir:
            file_parts = file.split('.')
            if file_parts[len(file_parts)-1] == "tcl":
                tcls.append(file)
        if len(tcls) == 0:
            return None
        if len(tcls) > 1:
            p.rawprint("Multiple tcls in the current directory!")
            p.rawprint(str(tcls))
            quit()
        return tcls[0]

    def __generate_tcl(self):
        fname = "run.tcl"
        f = open(fname,"w");
        f.write("project open " + self.modules_pool.get_top_module().syn_project + '\n')
        f.write("process run {Generate Programming File} -force rerun_all\n")
        f.close()
        return fname
        

    def generate_fetch_makefile(self):
        pool = self.modules_pool

        if pool.get_fetchable_modules() == []:
            p.rawprint("There are no fetchable modules. No fetch makefile is produced")
            quit()

        if not pool.is_everything_fetched():
            p.echo("A module remains unfetched. Fetching must be done prior to makefile generation")
            quit()
        self.make_writer.generate_fetch_makefile(pool)
