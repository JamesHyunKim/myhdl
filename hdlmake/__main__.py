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


from __future__ import print_function
import os
import importlib
import global_mod
import argparse
import logging
import sys
from util.termcolor import colored
from manifest_parser import ManifestParser
from module_pool import ModulePool
from env import Env
import fetch as fetch_mod
from action import (CheckCondition, CleanModules, FetchModules, GenerateFetchMakefile, ListFiles,
                    ListModules, MergeCores, GenerateSimulationMakefile,
                    GenerateSynthesisMakefile, GenerateRemoteSynthesisMakefile, GenerateSynthesisProject)

#from argument_parser import get_argument_parser

#try:
#    from build_hash import BUILD_ID
#except:
#    BUILD_ID = "unrecognized"


def main():
    """This is the main funcion, where HDLMake starts.
    Here, we make the next processes:
        -- parse command
        -- check and set the environment
        -- prepare the global module containing the heavy common stuff
    """	


    #
    # SET & GET PARSER
    #
    parser = _get_parser()

    #
    # PARSE & GET OPTIONS
    #
    options = _get_options(sys, parser)
    global_mod.options = options


    # global_mod_assigned!!!
    env = Env(options)
    global_mod.env = env


    numeric_level = getattr(logging, options.log.upper(), None)
    if not isinstance(numeric_level, int):
        sys.exit('Invalid log level: %s' % options.log)

    logging.basicConfig(format=colored("%(levelname)s", "yellow") + colored("\t%(filename)s:%(lineno)d: %(funcName)s()\t", "blue") + "%(message)s", level=numeric_level)
    logging.debug(str(options))

    modules_pool = ModulePool()
    modules_pool.new_module(parent=None,
                            url=os.getcwd(),
                            source=fetch_mod.LOCAL,
                            fetchto=".",
                            process_manifest=False)

    # Setting top_module as top module of design (ModulePool class)
    if modules_pool.get_top_module().manifest is None:
        logging.info("No manifest found. At least an empty one is needed")
        logging.info("To see some help, type hdlmake --help")
        sys.exit("Exiting")

    # Setting global variable (global_mod.py)
    top_mod = modules_pool.get_top_module()
    global_mod.top_module = top_mod

    #global_mod.global_target = global_mod.top_module.target
    global_mod.mod_pool = modules_pool

    modules_pool.process_top_module_manifest()

    #
    # Load global tool object (global_mod.py)
    #
    if top_mod.action == "synthesis":
        tool_name = top_mod.syn_tool
    elif top_mod.action == "simulation":
        tool_name = top_mod.sim_tool
    logging.info('import tool module: ' + tool_name)
    try:
        tool_module = importlib.import_module("tools.%s.%s" % (tool_name, tool_name))
    except Exception as e:
        logging.error(e)
        quit()

    global_mod.tool_module = tool_module


    #env.top_module = modules_pool.get_top_module()
    env.check_env(verbose=False)
    #env.check_env_wrt_manifest(verbose=False)


    #                                   #
    # EXECUTE THE COMMANDS/ACTIONS HERE #
    #                                   #


    if options.command == "check-env":
        env.check_env(verbose=True)
        quit()

    if options.command == "check-manifest":
        env.check_manifest(modules_pool.get_top_module().manifest, verbose=True)
        quit()

    if options.command == "manifest-help":
        ManifestParser().print_help()
        quit()

    if options.command == "auto":
        logging.info("Running automatic flow.")
        if not top_mod.action:
            logging.error("`action' manifest variable has to be specified. "
                          "Otherwise hdlmake doesn't know how to handle the project")
            quit()
        if top_mod.action == "simulation":
            if not top_mod.sim_tool:
                logging.error("`sim_tool' manifest variable has to be specified. "
                              "Otherwise hdlmake doesn't know how to simulate the project")
                quit()
            action = [ GenerateSimulationMakefile ]
        elif top_mod.action == "synthesis":
            if not top_mod.syn_tool:
                logging.error("`syn_tool' manifest variable has to be specified. "
                              "Otherwise hdlmake doesn't know how to synthesize the project")
                quit()
            action = [
                GenerateSynthesisProject,
                GenerateSynthesisMakefile,
                GenerateRemoteSynthesisMakefile
            ]
            
            # TODO: I advocate for removing the remote options -- too much pain, too little gain!!
            # Why shouldn't we directly use ssh, screen, scp and rsync on a remote HDLMake deployment??

    #elif options.command == "make-simulation":
    #    action = [ GenerateSimulationMakefile ]
    #elif options.command == "make-fetch":
    #    action = [ GenerateFetchMakefile ]
    #elif options.command == "make-ise":
    #    action = [ GenerateSynthesisMakefile ]
    #elif options.command == "make-remote":
    #    action = [ GenerateRemoteSynthesisMakefile ]
    elif options.command == "fetch":
        action = [ FetchModules ]
    elif options.command == "clean":
        action = [ CleanModules ]
    elif options.command == "list-mods":
        action = [ ListModules ]
    elif options.command == "list-files":
        action = [ ListFiles ]
    elif options.command == "merge-cores":
        action = [ MergeCores ]
    elif options.command == "ise-project":
        action = [ GenerateSynthesisProject ]
    elif options.command == "quartus-project":
        action = [ GenerateSynthesisProject ]
    elif options.command == "project":
        action = [ GenerateSynthesisProject ]

    try:
        for command in action:
            action_instance = command(modules_pool=modules_pool,
                                    options=options,
                                    env=env)
            action_instance.run()
    except Exception as e:
        import traceback
        logging.error(e)
        print("Trace:")
        traceback.print_exc()


def _get_parser():
    """This is the parser function, where options and commands are defined.
    Here, we make the next processes:
    """	

    usage = """hdlmake [command] [options]"""
    description = """Release 2014\n
        To see optional arguments for particular command type:
        hdlmake <command> --help
\0
"""

    parser = argparse.ArgumentParser("hdlmake",
                                     usage=usage,
                                     description=description)
    subparsers = parser.add_subparsers(title="commands", dest="command")

    check_env = subparsers.add_parser("check-env",
                                      help="check environment for HDLMAKE-related settings",
                                      description="Look for environmental variables specific for HDLMAKE.\n"
                                                  "Hdlmake will examine presence of supported synthesis and simulation"
                                                  "tools.\n")
    # check_manifest = subparsers.add_parser("check-manifest", help="check manifest for formal correctness")
    # check_manifest.add_argument("--top", help="indicate path to the top manifest", default=None)
    manifest_help = subparsers.add_parser("manifest-help", help="print manifest file variables description")

    fetch = subparsers.add_parser("fetch", help="fetch and/or update remote modules listed in Manifest")
    fetch.add_argument("--flatten", help="`flatten' modules' hierarchy by storing everything in top module's fetchto direactoru",
                       default=False, action="store_true")
    fetch.add_argument("--update", help="force updating of the fetched modules", default=False, action="store_true")
    clean = subparsers.add_parser("clean", help="remove all modules fetched for direct and indirect children of this module")
    listmod = subparsers.add_parser("list-mods", help="List all modules together with their files")
    listmod.add_argument("--with-files", help="list modules together with their files", default=False, action="store_true", dest="withfiles")
    listfiles = subparsers.add_parser("list-files", help="List all files in a form of a space-separated string")
    listfiles.add_argument("--delimiter", help="set delimitier for the list of files", dest="delimiter", default=' ')
    merge_cores = subparsers.add_parser("merge-cores", help="Merges entire synthesizable content of an project into a pair of VHDL/Verilog files")
    merge_cores.add_argument("--dest", help="name for output merged file", dest="dest", default=None)
    ise_proj = subparsers.add_parser("ise-project", help="create/update an ise project including list of project")
    ise_proj.add_argument("--generate-project-vhd", help="generate project.vhd file with a meta package describing the project",
                          dest="generate_project_vhd", default=False, action="store_true")
    quartus_proj = subparsers.add_parser("quartus-project", help="create/update a quartus project including list of project")
    synthesis_proj = subparsers.add_parser("project", help="create/update a project for the appropriated tool")

    condition_check = argparse.ArgumentParser()
    condition_check.add_argument("--tool", dest="tool", required=True)
    condition_check.add_argument("--reference", dest="reference", required=True)
    condition_check.add_argument("--condition", dest="condition", required=True)

    auto = subparsers.add_parser("auto", help="default action for hdlmake. Run when no args are given")
    auto.add_argument("--force", help="force hdlmake to generate the makefile, even if the specified tool is missing", default=False, action="store_true")
    auto.add_argument("--noprune", help="prevent hdlmake from pruning unneeded files", default=False, action="store_true")
    auto.add_argument("--generate-project-vhd", help="generate project.vhd file with a meta package describing the project",
                      dest="generate_project_vhd", default=False, action="store_true")

    parser.add_argument("--py", dest="arbitrary_code",
                        default="", help="add arbitrary code when evaluation all manifests")

    parser.add_argument("--log", dest="log",
                        default="info", help="set logging level (one of debug, info, warning, error, critical")
    parser.add_argument("--generate-project-vhd", help="generate project.vhd file with a meta package describing the project",
                          dest="generate_project_vhd", default=False, action="store_true")
    parser.add_argument("--force", help="force hdlmake to generate the makefile, even if the specified tool is missing", default=False, action="store_true")

    return parser



def _get_options(sys,parser):
    options = None
    if len(sys.argv[1:]) == 0:
            options = parser.parse_args(['auto'])

    elif len(sys.argv[1:]) == 1:
        if sys.argv[1] == "_conditioncheck":
            options = condition_check.parse_args(sys.argv[2:])
            env = Env(options)
            env.check_env()
            CheckCondition(modules_pool=None,
                           options=options,
                           env=env).run()
            quit()
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            options = parser.parse_args(sys.argv[1:])
        elif sys.argv[1].startswith('-'):
            options = parser.parse_args(["auto"]+sys.argv[1:])
        else:
            options = parser.parse_args(sys.argv[1:])
    else:
        options = parser.parse_args(sys.argv[1:])
    return options



if __name__ == "__main__":
    main()
