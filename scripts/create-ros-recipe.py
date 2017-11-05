#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016 David Bensoussan, Synapticon GmbH
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal  in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#

"""
This script creates Yocto recipe for ROS software.
It takes as an input repository owner, name and tag
"""

import re
import hashlib
import urllib
import tarfile
import sys
import os
import shutil
from lxml import etree


def print_usage():
    print "Usage of commands:\n"
    print "-h/--help"
    print "-g <repository-name> <package-name> <package-version>"
    print "  Example: python create_ros_recipe.py -g OctoMap octomap-ros 0.4.0"


def print_commands():
    print "Summary of commands:\n"
    print "-h/--help                        - prints commands and example"
    print "-g/--generates                   - generates recipe of ros package"


def correct(string):
    return re.sub(r'\.(?! )', '. ', re.sub(r' +', ' ',
                                           re.sub(r'\n', '', string)))


class xml_parser:

    def __init__(self, xml_path):
        self.xml_path = xml_path
        self.tree = etree.parse(self.xml_path)

    def get_name(self):
        return self.tree.xpath("/package/name")[0].text

    def get_version(self):
        return self.tree.xpath("/package/version")[0].text

    def get_description(self):
        return correct(
            self.tree.xpath("/package/description")[0].text).lstrip(' ')

    def get_author_name(self):
        return self.tree.xpath("/package/author")[0].text

    def get_license(self):
        return self.tree.xpath("/package/license")[0].text

    def get_build_dependencies(self):
        build_dependencies = []
        for dependency in self.tree.xpath("/package/build_depend"):
            build_dependencies.append(dependency.text.replace("_", "-"))
        return build_dependencies

    def get_run_dependencies(self):
        run_dependencies = []
        for dependency in self.tree.xpath("/package/run_depend"):
            run_dependencies.append(dependency.text.replace("_", "-"))
        return run_dependencies

    def get_license_line_number(self):
        with open(self.xml_path) as file:
            for num, line in enumerate(file, 1):
                if 'license' in line:
                    return num
            return 'CLOSED'


class yocto_recipe:

    def __init__(self, repository, name, version):
        self.name = name
        self.repository = repository
        self.version = version
        self.description = None
        self.url = None
        self.author = None
        self.license = None
        self.build_dependencies = None
        self.license_line = None
        self.license_md5 = None
        self.src_md5 = None
        self.src_sha256 = None

    def get_license_MD5(self, license):
        if license == "BSD":
            return "d566ef916e9dedc494f5f793a6690ba5"
        elif license == "Mozilla Public License Version 1.1":
            return "e1b5a50d4dd59d8102e41a7a2254462d"
        elif license == "CC-BY-NC-SA-2.0":
            return "11e24f757f025b2cbebd5b14b4a7ca19"
        elif license == "LGPL-2.1":
            return "184dd1523b9a109aead3fbbe0b4262e0"
        elif license == "GPL":
            return "162b49cfbae9eadf37c9b89b2d2ac6be"
        elif license == "LGPL-2.1+":
            return "58d727014cda5ed405b7fb52666a1f97"
        elif license == "LGPLv2":
            return "46ee8693f40a89a31023e97ae17ecf19"
        elif license == "MIT":
            return "58e54c03ca7f821dd3967e2a2cd1596e"

    def get_src_MD5(self):
        hash_md5 = hashlib.md5()
        with open(self.getArchiveName(), "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_src_sha256(self):
        return hashlib.sha256(
            open("./" + self.getArchiveName(), 'rb').read()).hexdigest()

    def import_XML(self):
        xml = xml_parser(self.getFolderName() + "/package.xml")
        self.description = xml.get_description()
        self.author = xml.get_author_name()
        self.license = xml.get_license()
        self.build_dependencies = xml.get_build_dependencies()
        self.run_dependencies = xml.get_run_dependencies()
        self.license_line = xml.get_license_line_number()
        self.license_md5 = self.get_license_MD5(self.license)

    def get_URL(self):
        return os.path.join(
            "https://github.com",
            self.repository,
            self.name.replace("-", "_"),
            "archive",
            str(self.version)) + ".tar.gz"

    def getFolderName(self):
        return self.name.replace("-", "_") + "-" + str(self.version)

    def getArchiveName(self):
        return self.name.replace("-", "_") + \
            "-" + str(self.version) + \
            ".tar.gz"

    # To debug
    def print_XML(self):
        print self.name
        print self.version
        print self.description
        print self.author
        print self.license
        print self.build_dependencies
        print self.run_dependencies

    def parse_build_dependencies(self):
        if self.build_dependencies:
            build_dependencies = ''.join(['DEPENDS = \"',' '.join(self.build_dependencies), "\"", "\n"])
            return build_dependencies
        return ""

    def parse_run_dependencies(self):
        if self.run_dependencies:
            run_dependencies = ''.join(['RDEPENDS_${PN} = \"',' '.join(self.run_dependencies), "\"", "\n"])
            return run_dependencies
        return ""

    def download_archive(self):
        urllib.urlretrieve(self.get_URL(), self.getArchiveName())

    def extract_archive(self):
        tar = tarfile.open(self.getArchiveName(), "r:gz")
        tar.extractall()
        tar.close()

    def delete_source(self):
        os.remove(self.getArchiveName())
        shutil.rmtree('-'.join([self.name, str(self.version)]))

    def create_recipe(self):
        filename = self.name.replace("_", "-") + "_" + self.version + ".bb"
        print "Recipe generated:\n" + filename
        f = open(self.name.replace("_", "-") + "_" + self.version + ".bb", "w")

        f.write('DESCRIPTION = \"' + self.description.rstrip() + "\"\n")
        f.write('AUTHOR = \"' + self.author + '\"\n')
        f.write('SECTION = \"devel\"\n')
        f.write('LICENSE = \"' + self.license + "\"\n")
        f.write(
            ''.join([
                'LIC_FILES_CHKSUM = \"file://package.xml;beginline=',
                str(self.license_line),
                ";endline=",
                str(self.license_line),
                ";md5=",
                self.license_md5,
                "\"\n"])
        )
        f.write('\n')

        f.write(self.parse_build_dependencies() + "\n")
        f.write(self.parse_run_dependencies() + "\n")
        f.write(
            ''.join([
                "SRC_URI = ", "\"https://github.com/", self.repository,
                "/${ROS_SPN}/archive/${PV}.tar.gz;",
                "downloadfilename=${ROS_SP}.tar.gz\"\n"])
        )
        f.write(''.join(["SRC_URI[md5sum] = \"", self.get_src_MD5(), "\"\n"]))
        f.write(
            ''.join(["SRC_URI[sha256sum] = \"", self.get_src_sha256(), "\"\n"]))

        f.write('\n')
        f.write('S = \"${WORKDIR}/${ROS_SP}\"\n')
        f.write('\n')

        f.write('inherit catkin\n')
        f.close()


if __name__ == '__main__':
    if sys.argv[1] == "-h" or sys.argv[1] == "--help":
        print_commands()
        print_usage()
    if sys.argv[1] == "-g" or sys.argv[1] == "--generate":
        if len(sys.argv) == 5:
            recipe = yocto_recipe(sys.argv[2], sys.argv[3], sys.argv[4])
            recipe.download_archive()
            recipe.extract_archive()
            recipe.import_XML()
            recipe.create_recipe()
            recipe.delete_source()
        else:
            print "Please provide 3 arguments"
            print_usage()
            print_commands()
    else:
        print "Please provide 3 arguments"
        print_usage()
        print_commands()
