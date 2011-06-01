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


import xml.dom.minidom
import msg as p

xmlimpl = xml.dom.minidom.getDOMImplementation()

class QuartusProject:
    class QuartusProjectProperty:
        SET_GLOBAL_INSTANCE, SET_INSTANCE_ASSIGNMENT, SET_LOCATION_ASSIGNMENT, SET_GLOBAL_ASSIGNMENT = range(4)
        t = {"set_global_instance" : SET_GLOBAL_INSTANCE,
        "set_instance_assignment" : SET_INSTANCE_ASSIGNMENT,
        "set_location_assignment": SET_LOCATION_ASSIGNMENT,
        "set_global_assignment": SET_GLOBAL_ASSIGNMENT}

        def __init__(self, command, what=None, name=None, name_type=None, from_=None, to=None, section_id=None):
            self.command = command
            self.what = what
            self.name = name
            self.name_type = name_type
            self.from_ = from_
            self.to = to
            self.section_id = section_id

        def emit(self):
            words = []
            words.append(dict([(b,a) for a,b in self.t.items()])[self.command])

            if self.what != None:
                words.append(self.what)
            if self.name != None:
                words.append("-name")
                words.append(self.name_type)
                words.append(self.name)
            if self.from_ != None:
                words.append("-from")
                words.append(self.from_)
            if self.to != None:
                words.append("-to")
                words.append(self.to)
            if self.section_id != None:
                words.append("-section_id")
                words.append(self.section_id)
            return ' '.join(words)

    def __init__(self, filename):
        self.properties = []
        self.files = []
        self.filename = filename
        self.preflow = None
        self.postflow = None

    def emit(self):
        f = open(self.filename+'.qsf', "w")
        for p in self.properties:
            f.write(p.emit()+'\n')
        f.write(self.__emit_files())
        f.write(self.__emit_scripts())
        f.close()

    def __emit_scripts(self):
        tmp = 'set_global_assignment -name {0} "quartus_sh:{1}"'
        pre = post = ""
        if self.preflow:
            pre = tmp.format("PRE_FLOW_SCRIPT_FILE", self.preflow.rel_path())
        if self.postflow:
            post = tmp.format("POST_FLOW_SCTIPT_FILE", self.postflow.rel_path())
        return pre+'\n'+post+'\n'
        
    def __emit_files(self):
        from srcfile import VHDLFile, VerilogFile, SignalTapFile, DPFFile
        tmp = "set_global_assignment -name {0} {1}"
        ret = []
        for f in self.files:
            if isinstance(f, VHDLFile):
                line = tmp.format("VHDL_FILE", f.rel_path())
            elif isinstance(f, VerilogFile):
                line = tmp.format("VERILOG_FILE", f.rel_path())
            elif isinstance(f, SignalTapFile):
                line = tmp.format("SIGNALTAP_FILE", f.rel_path())
            elif isinstance(f, DPFFile):
                line = tmp.format("MISC_FILE", f.rel_path())
            else:
                continue
            ret.append(line)
        return ('\n'.join(ret))+'\n'
 
    def add_property(self, val):
        #don't save files (they are unneeded)
        if val.name_type != None and "_FILE" in val.name_type:
            return
        self.properties.append(val)

    def add_files(self, fileset):
        for f in fileset:
            self.files.append(f)

    def read(self):
        def __gather_string(words, first_index):
            i = first_index
            ret = []
            if words[i][0] != '"':
                return (words[i],1)
            else:
                while True:
                    ret.append(words[i])
                    if words[i][len(words[i])-1] == '"':
                        return (' '.join(ret), len(ret))
                    i=i+1

        f = open(self.filename+'.qsf', "r")
        lines = [l.strip() for l in f.readlines()]
        lines = [l for l in lines if l != "" and l[0] != '#']
        qpp = QuartusProject.QuartusProjectProperty
        for line in lines:
            words = line.split()
            command = qpp.t[words[0]]
            what = name = name_type = from_ = to = section_id = None
            i = 1
            while True:
                if i >= len(words):
                    break

                if words[i] == "-name":
                    name_type = words[i+1]
                    name, add = __gather_string(words, i+2)
                    print name
                    i = i+2+add
                    continue
                elif words[i] == "-section_id":
                    section_id, add = __gather_string(words, i+1)
                    i = i+1+add
                    continue
                elif words[i] == "-to":
                    to, add = __gather_string(words, i+1)
                    i = i+1+add
                    continue
                elif words[i] == "-from":
                    from_, add = __gather_string(words, i+1)
                    i = i+2
                    continue
                else:
                    what = words[i]
                    i = i+1
                    continue
            prop = self.QuartusProjectProperty(command=command, what=what, name=name, name_type=name_type, from_=from_,
            to=to, section_id=section_id)

            self.add_property(prop)
        f.close()

class ISEProject:

    class ISEProjectProperty:
        def __init__(self,  name, value, is_default = False):
                self.name = name
                self.value = value
                self.is_default = is_default

        def emit_xml(self, doc):
                prop = doc.createElement("property")
                prop.setAttribute("xil_pn:name", self.name)
                prop.setAttribute("xil_pn:value", self.value)
                if self.is_default:
                        prop.setAttribute("xil_pn:valueState", "default")
                else:
                        prop.setAttribute("xil_pn:valueState", "non-default")

                return prop

    def __init__(self, ise, top_mod = None):
            self.props = []
            self.files = []
            self.libs = []
            self.xml_doc = None
            self.xml_files = []
            self.xml_props = []
            self.xml_libs = []
            self.xml_ise = None
            self.top_mod = top_mod
            self.ise = ise

    def add_files(self, files):
            self.files.extend(files);

    def __add_lib(self, lib):
        if lib not in self.libs:
            self.libs.append(lib)

    def add_libs(self, libs):
            for l in libs:
                self.__add_lib(l)
            self.libs.remove('work')

    def add_property(self, prop):
            self.props.append(prop)

    def __parse_props(self):
            for xmlp in self.xml_project.getElementsByTagName("properties")[0].getElementsByTagName("property"):
                    prop = self.ISEProjectProperty(
                            xmlp.getAttribute("xil_pn:name"),
                            xmlp.getAttribute("xil_pn:value"),
                            xmlp.getAttribute("xil_pn:valueState") == "default"
                            )

                    self.props.append(prop)
            self.xml_props = self.__purge_dom_node(name="properties", where=self.xml_doc.documentElement)

    def __parse_libs(self):
            for l in self.xml_project.getElementsByTagName("libraries")[0].getElementsByTagName("library"):
                    self.__add_lib(l.getAttribute("xil_pn:name"))
            self.xml_libs = self.__purge_dom_node(name="libraries", where=self.xml_doc.documentElement)

    def load_xml(self, filename):
            f = open(filename)
            self.xml_doc = xml.dom.minidom.parse(f)
            self.xml_project =  self.xml_doc.getElementsByTagName("project")[0];
            import sys
            try:
                self.__parse_props()
            except xml.parsers.expat.ExpatError:
                p.rawprint("Error while parsing existng file's properties:")
                p.rawprint(str(sys.exc_info()))
                quit()

            try:
                self.__parse_libs()
            except xml.parsers.expat.ExpatError:
                p.rawprint("Error while parsing existng file's libraries:")
                p.rawprint(str(sys.exc_info()))
                quit()
                
            where = self.xml_doc.documentElement
            self.xml_files = self.__purge_dom_node(name="files", where=where)
            node = where.getElementsByTagName("version")[0]
            where.removeChild(node)
            f.close()

    def __purge_dom_node(self, name, where):
            node = where.getElementsByTagName(name)[0]
            where.removeChild(node)
            new = self.xml_doc.createElement(name)
            where.appendChild(new)
            return new

    def __output_files(self, node):

            for f in self.files:
                    import os
                    from srcfile import UCFFile, VHDLFile, VerilogFile
                    fp = self.xml_doc.createElement("file")
                    fp.setAttribute("xil_pn:name", os.path.relpath(f.path))
                    if (isinstance(f, VHDLFile)):
                            fp.setAttribute("xil_pn:type", "FILE_VHDL")
                    elif (isinstance(f, VerilogFile)):
                            fp.setAttribute("xil_pn:type", "FILE_VERILOG")
                    elif (isinstance(f, UCFFile)):
                            fp.setAttribute("xil_pn:type", "FILE_UCF")

                    assoc = self.xml_doc.createElement("association");
                    assoc.setAttribute("xil_pn:name", "Implementation");
                    assoc.setAttribute("xil_pn:seqID", str(self.files.index(f)+1));

                    if(f.library != "work"):
                            lib = self.xml_doc.createElement("library");
                            lib.setAttribute("xil_pn:name", f.library);
                            fp.appendChild(lib)

                    fp.appendChild(assoc)
                    node.appendChild(fp);

    def __output_props(self, node):
            for p in self.props:
                    node.appendChild(p.emit_xml(self.xml_doc))

    def __output_libs(self, node):
            for l in self.libs:
                    ll =  self.xml_doc.createElement("library")
                    ll.setAttribute("xil_pn:name", l);
                    node.appendChild(ll);

    def __output_ise(self, node):
        i = self.xml_doc.createElement("version")
        i.setAttribute("xil_pn:ise_version", str(self.ise))
        i.setAttribute("xil_pn:schema_version", "2")
        node.appendChild(i)

    def emit_xml(self, filename = None):

            if not self.xml_doc:
                    self.create_empty_project()
            else:
                    self.__output_ise(self.xml_doc.documentElement)
            self.__output_files(self.xml_files)
            self.__output_props(self.xml_props)
            self.__output_libs(self.xml_libs)
            self.xml_doc.writexml(open(filename,"w"), newl="\n", addindent="\t")


    def create_empty_project(self):
            self.xml_doc = xmlimpl.createDocument("http://www.xilinx.com/XMLSchema", "project", None)
            top_element = self.xml_doc.documentElement
            top_element.setAttribute("xmlns", "http://www.xilinx.com/XMLSchema")
            top_element.setAttribute("xmlns:xil_pn", "http://www.xilinx.com/XMLSchema")

            version = self.xml_doc.createElement( "version")
            version.setAttribute("xil_pn:ise_version", self.ise);
            version.setAttribute("xil_pn:schema_version", "2");

            header = self.xml_doc.createElement("header")
            header.appendChild(self.xml_doc.createTextNode(""))

            self.xml_files = self.xml_doc.createElement("files")
            self.xml_props = self.xml_doc.createElement("properties")
            self.xml_libs = self.xml_doc.createElement("libraries")

            top_element.appendChild(header)
            top_element.appendChild(version)
            top_element.appendChild(self.xml_files)
            top_element.appendChild(self.xml_props)
            top_element.appendChild(self.xml_libs)
