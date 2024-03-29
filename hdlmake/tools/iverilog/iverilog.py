#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013, 2014 CERN
# Author: Pawel Szostek (pawel.szostek@cern.ch)
# Multi-tool support by Javier D. Garcia-Lasheras (javier@garcialasheras.com)
#
# This file is part of Hdlmake.
#
# Hdlmake is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hdlmake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Hdlmake.  If not, see <http://www.gnu.org/licenses/>.
#

from subprocess import Popen, PIPE

import string
from string import Template
import fetch

from makefile_writer import MakefileWriter


IVERILOG_STANDARD_LIBS = ['std', 'ieee', 'ieee_proposed', 'vl', 'synopsys',
                      'simprim', 'unisim', 'unimacro', 'aim', 'cpld',
                      'pls', 'xilinxcorelib', 'aim_ver', 'cpld_ver',
                      'simprims_ver', 'unisims_ver', 'uni9000_ver',
                      'unimacro_ver', 'xilinxcorelib_ver', 'secureip']

class ToolControls(MakefileWriter):


    def get_keys(self):
        tool_info = {
            'name': 'Icarus Verilog',
            'id': 'iverilog',
            'windows_bin': 'iverilog',
            'linux_bin': 'iverilog'
        }
        return tool_info

    def get_standard_libraries(self):
        return IVERILOG_STANDARD_LIBS

    def detect_version(self, path):
        iverilog = Popen("iverilog -v 2>/dev/null| awk '{if(NR==1) print $4}'",
                         shell=True,
                         stdin=PIPE,
                         stdout=PIPE,
                         close_fds=True)
        version = iverilog.stdout.readlines()[0].strip()
        return version


    def generate_simulation_makefile(self, fileset, top_module):
        # TODO FLAGS: 2009 enables SystemVerilog (ongoing support) and partial VHDL support

        # TODO: include dir
        
        from srcfile import VerilogFile, VHDLFile, SVFile

        makefile_tmplt_1 = string.Template("""TOP_MODULE := ${top_module}
IVERILOG_CRAP := \
run.command

#target for performing local simulation
sim: sim_pre_cmd
""")

        makefile_text_1 = makefile_tmplt_1.substitute(
            top_module=top_module.top_module
        )
        self.write(makefile_text_1)

        self.writeln("\t\techo \"# IVerilog command file, generated by HDLMake\" > run.command")

        for vl in fileset.filter(VerilogFile):
            self.writeln("\t\techo \"" + vl.rel_path() + "\" >> run.command")

        for vhdl in fileset.filter(VHDLFile):
            self.writeln("\t\techo \"" + vhdl.rel_path() + "\" >> run.command")

        for sv in fileset.filter(SVFile):
            self.writeln("\t\techo \"" + sv.rel_path() + "\" >> run.command")


        makefile_tmplt_2 = string.Template("""      
\t\tiverilog -s $$(TOP_MODULE) -o $$(TOP_MODULE).vvp -c run.command

sim_pre_cmd:
\t\t${sim_pre_cmd}

sim_post_cmd: sim
\t\t${sim_post_cmd}

#target for cleaning all intermediate stuff
clean:
\t\trm -rf $$(IVERILOG_CRAP)

#target for cleaning final files
mrproper: clean
\t\trm -f *.vcd *.vvp

.PHONY: mrproper clean sim sim_pre_cmd sim_post_cmd

""")
        if top_module.sim_pre_cmd:
            sim_pre_cmd = top_module.sim_pre_cmd
        else:
            sim_pre_cmd = ''

        if top_module.sim_post_cmd:
            sim_post_cmd = top_module.sim_post_cmd
        else:
            sim_post_cmd = ''

        makefile_text_2 = makefile_tmplt_2.substitute(
            sim_pre_cmd=sim_pre_cmd,
            sim_post_cmd=sim_post_cmd,
        )
        self.write(makefile_text_2)


    # Below is the old makefile generator: I'll keep it for some time while testing

    def generate_iverilog_makefile(self, fileset, top_module, modules_pool):
        print('javi checkpoint 0')
        from srcfile import VerilogFile

        for f in global_mod.top_module.incl_makefiles:
            self.writeln("include " + f)
        target_list = []
        for vl in fileset.filter(VerilogFile):
            rel_dir_path = os.path.dirname(vl.rel_path())
            if rel_dir_path:
                rel_dir_path = rel_dir_path + '/'
            target_name = os.path.join(rel_dir_path+vl.purename)
            target_list.append(target_name)

            dependencies_string = ' '.join([f.rel_path() for f in vl.depends_on if (f.name != vl.name)])
            include_dirs = list(set([os.path.dirname(f.rel_path()) for f in vl.depends_on if f.name.endswith("vh")]))
            while "" in include_dirs:
                include_dirs.remove("")
            include_dir_string = " -I".join(include_dirs)
            if include_dir_string:
                include_dir_string = ' -I'+include_dir_string
                self.writeln("VFLAGS_"+target_name+"="+include_dir_string)
            self.writeln('# jd checkpoint')
            self.writeln(target_name+"_deps = "+dependencies_string)
        print('javi target_list', target_list)

        sim_only_files = []
        for m in global_mod.mod_pool:
            for f in m.sim_only_files:
                sim_only_files.append(f.name)
        print('javi sim_only_files', sim_only_files)

        # bit file targets are those that are only used in simulation
        bit_targets = []
        for m in global_mod.mod_pool:
            bit_targets = bit_targets + list(m.bit_file_targets)
        print('javi bit_targets', bit_targets)

        for bt in bit_targets:
            bt = bt.purename
            bt_syn_deps = []
            # This can perhaps be done faster (?)
            for vl in fileset.filter(VerilogFile):
                if vl.purename == bt:
                    for f in vl.depends_on:
                        if (f.name != vl.name and f.name not in sim_only_files):
                            bt_syn_deps.append(f)
            self.writeln(bt+'syn_deps = '+ ' '.join([f.rel_path() for f in bt_syn_deps]))
            if not os.path.exists("%s.ucf" % bt):
                logging.warning("The file %s.ucf doesn't exist!" % bt)
            self.writeln(bt+".bit:\t"+bt+".v $("+bt+"syn_deps) "+bt+".ucf")
            part=(global_mod.top_module.syn_device+'-'+
                  global_mod.top_module.syn_package+
                  global_mod.top_module.syn_grade)
            self.writeln("\tPART="+part+" $(SYNTH) "+bt+" $^")
            self.writeln("\tmv _xilinx/"+bt+".bit $@")

        self.writeln("clean:")
        self.writeln("\t\trm -f "+" ".join(target_list)+"\n\t\trm -rf _xilinx")


