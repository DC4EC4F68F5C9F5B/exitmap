#!/usr/bin/env python

# Copyright 2014, 2015 Philipp Winter <phw@nymity.ch>
# Copyright 2014 Josh Pitts <josh.pitts@leviathansecurity.com>
#
# This file is part of exitmap.
#
# exitmap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# exitmap is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with exitmap.  If not, see <http://www.gnu.org/licenses/>.

"""
patchingCheck.py
by Joshua Pitts josh.pitts@leviathansecurity.com
twitter: @midnite_runr

Module to detect binary patching.

-USAGE-
Make appropriate changes in the EDIT ME SECTION

Then run:
./bin/exitmap -d 5 patchingCheck

"""

import sys
import os
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2
import tempfile
import log
import hashlib

import util

logger = log.get_logger()

#######################
# EDIT ME SECTION START
#######################

# EDIT ME: exitmap needs this variable to figure out which
# relays can exit to the given destination(s).

destinations = [("live.sysinternals.com", 80)]

# Only test one binary at a time
# Must provide a Download link
check_files = {
    "http://live.sysinternals.com/psexec.exe": [None, None],
    # "http://www.ntcore.com/files/ExplorerSuite.exe": [None, None],
}

# Set UserAgent
# Reference: http://www.useragentstring.com/pages/Internet%20Explorer/
test_agent = 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)'

#######################
# EDIT ME SECTION END
#######################


def setup():
    """
    Perform one-off setup tasks, i.e., download reference files.
    """

    logger.info("Creating temporary reference files.")

    for url, _ in check_files.iteritems():

        logger.debug("Attempting to download <%s>." % url)

        request = urllib2.Request(url)
        request.add_header('User-Agent', test_agent)

        try:
            data = urllib2.urlopen(request).read()
        except Exception as err:
            logger.warning("urlopen() failed: %s" % err)

        file_name = url.split("/")[-1]
        _, tmp_file = tempfile.mkstemp(prefix="exitmap_%s_" % file_name)

        with open(tmp_file, "wb") as fd:
            fd.write(data)

        logger.debug("Wrote file to \"%s\"." % tmp_file)

        check_files[url] = [tmp_file, sha512_file(tmp_file)]


def teardown():
    """
    Perform one-off teardown tasks, i.e., remove reference files.
    """

    logger.info("Removing reference files.")

    for _, file_info in check_files.iteritems():

        orig_file, _ = file_info
        logger.info("Removing file \"%s\"." % orig_file)
        os.remove(orig_file)


def sha512_file(file_name):
    """
    Calculate SHA512 over the given file.
    """

    hash_func = hashlib.sha256()

    with open(file_name, "rb") as fd:
        hash_func.update(fd.read())

    return hash_func.hexdigest()


def files_identical(observed_file, original_file):
    """
    Return True if the files are identical and False otherwise.

    This check is necessary because sometimes file transfers are terminated
    before they are finished and we are left with an incomplete file.
    """

    observed_length = os.path.getsize(observed_file)
    original_length = os.path.getsize(original_file)

    if observed_length >= original_length:
        return False

    with open(original_file) as fd:
        original_data = fd.read(observed_length)

    with open(observed_file) as fd:
        observed_data = fd.read()

    return original_data == observed_data


def run_check(exit_desc):
    """
    Download file and check if its checksum is as expected.
    """

    exiturl = util.exiturl(exit_desc.fingerprint)

    for url, file_info in check_files.iteritems():

        orig_file, orig_digest = file_info

        logger.debug("Attempting to download <%s> over %s." % (url, exiturl))

        data = None

        request = urllib2.Request(url)
        request.add_header('User-Agent', test_agent)

        try:
            data = urllib2.urlopen(request, timeout=20).read()
        except Exception as err:
            logger.warning("urlopen() failed for %s: %s" % (exiturl, err))
            continue

        if not data:
            logger.warning("No data received from <%s> over %s." %
                           (url, exiturl))
            continue

        file_name = url.split("/")[-1]
        _, tmp_file = tempfile.mkstemp(prefix="exitmap_%s_%s_" %
                                       (exit_desc.fingerprint, file_name))

        with open(tmp_file, "wb") as fd:
            fd.write(data)

        observed_digest = sha512_file(tmp_file)

        if (observed_digest != orig_digest) and \
           (not files_identical(tmp_file, orig_file)):

            logger.critical("File \"%s\" differs from reference file \"%s\".  "
                            "Downloaded over exit relay %s." %
                            (tmp_file, orig_file, exiturl))

        else:
            logger.debug("File \"%s\" fetched over %s as expected." %
                         (tmp_file, exiturl))

            os.remove(tmp_file)


def probe(exit_desc, run_python_over_tor, run_cmd_over_tor):
    """
    Probe the given exit relay and look for modified binaries.
    """

    run_python_over_tor(run_check, exit_desc)


def main():
    """
    Entry point when invoked over the command line.
    """

    setup()
    probe("dummy", None)
    teardown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
