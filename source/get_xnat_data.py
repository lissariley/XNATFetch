#!/usr/bin/env python

from __future__ import division, absolute_import, print_function
import os
import fnmatch
import socket
import argparse
import requests.packages.urllib3
import datetime
import logging
import shutil
import traceback
import re
import zipfile

try:
    # Attempt to load non-standard libraries
    import dateutil.parser
    # import numpy as np
    from pyxnat import Interface
except ModuleNotFoundError:
    # Alert user that they may have forgotten to load a virtualenvironment
    import sys

    stack_trace = traceback.format_exc()
    logging.critical(stack_trace)
    logging.critical('***********************************************************')
    logging.critical('***** Should you perhaps activate a virtualenv first? *****')
    logging.critical('***********************************************************')
    sys.exit()

requests.packages.urllib3.disable_warnings()

# Default server info, valid for ACLab in 5/2021
DEFAULT_XNAT_HOST = 'fh-mi-cmrifserv.human.cornell.edu'
DEFAULT_XNAT_PORT = '8080'
DEFAULT_XNAT_PATH = '/xnat'
DEFAULT_USER = os.environ['USER']

# Define mapping between verbosity user input and logging verbosity levels
VERBOSITY = {0 : logging.CRITICAL,
             1 : logging.WARNING,
             2 : logging.INFO,
             3 : logging.DEBUG}

def is_keeper(seriesDescription, series_keep_list=None, series_skip_list=None):
    """
    Checks a series description against keep and skip lists to determine if the
    resource should be fetched or not.

    Parameters
    -----------
    seriesDescription : str
        A data series description
    series_keep_list : list of str
        Series descriptions of files that should be kept
    series_skip_list : list of str
        Series descriptions of files that should be skipped

    Returns
    -------
    bool : should file be fetched?
    """

    if series_keep_list is not None:
        # Check if series description matches anything in the keep list
        keep = [f for f in series_keep_list if fnmatch.fnmatch(seriesDescription, f)]
        logging.debug('Series {seriesDescription} matches {n} keep elements'.format(seriesDescription=seriesDescription, n=len(keep)))
        return len(keep) > 0
    if series_skip_list is not None:
        # Check if series description matches anything in the skip list
        skip = [f for f in series_skip_list if fnmatch.fnmatch(seriesDescription, f)]
        logging.debug('Series {seriesDescription} matches {n} skip elements'.format(seriesDescription=seriesDescription, n=len(skip)))
        return len(skip) == 0
    # # We will get the file if it matches something in the keep list and not in the skip list OR if it doesn't match anything in either list.
    # return (keep and (not skip)) or ((not keep) and (not skip))

def fetch_and_organize_aux_files(exp, sub_path, aux_file_group_label,
    aux_files_fetch_list=[], aux_files_unzip_list=[], aux_files_org_regex=None,
    retain_unorganized_aux_files=True):
    # Get resource IDs associated with this experiment, so we can pull any
    #   desired auxiliary files. There should normally only be one
    #   experiment resource group.

    # Create a subdirectory in the base subject directory to contain auxiliary files.
    aux_path = os.path.join(sub_path, 'auxiliary_files')
    try:
        os.mkdir(aux_path)
    except FileExistsError:
        pass

    # Get list of resource IDs in this experiment (typically just one)
    resource_ids = exp.resources().get()
    if len(resource_ids) == 0:
        logging.critical('++ WARNING: Failed to get auxiliary resources '+
                         'for this subject - none appear to exist on the '+
                         'xnat server.')
        auxiliary_file_group = None
    else:
        resources = [
                exp.resource(resource_id)
                for resource_id in resource_ids
                if exp.resource(resource_id).label() == aux_file_group_label
            ]
        if len(resources) == 1:
            auxiliary_file_group = resources[0]
        elif len(resources) == 0:
            logging.critical('++ WARNING: This subject does not appear to '+
                            'have any subject resources called '+
                            '{aux_file_group_label}.'.format(aux_file_group_label=aux_file_group_label))
            auxiliary_file_group = None
        else:
            logging.critical('++ WARNING: This subject appears to have more '+
                             'than one subject resource called '+
                             '{aux_file_group_label}. Choosing first one.'.format(aux_file_group_label=aux_file_group_label))
            auxiliary_file_group = resources[0]

    if auxiliary_file_group is not None:
        # Get list of files within auxiliary file group
        auxiliary_filenames = auxiliary_file_group.files().get()

        # Filter list of files for the ones that the user wants to fetch
        matching_auxiliary_filenames = [
                auxiliary_filename for auxiliary_filename in auxiliary_filenames
                if any([
                    fnmatch.fnmatch(auxiliary_filename, pattern) for pattern in aux_files_fetch_list
                ])
            ]

        # Loop over filtered list of auxiliary files and fetch them
        logging.info('++ Fetching {n} auxiliary files.'.format(n=len(matching_auxiliary_filenames)))
        fetched_auxiliary_files = {}
        for auxiliary_filename in matching_auxiliary_filenames:
            auxiliary_filepath = os.path.join(aux_path, auxiliary_filename)
            if not os.path.exists(auxiliary_filepath):
                logging.info('++ Getting auxiliary file {aux_filename} and saving to {aux_path}'.format(aux_filename = auxiliary_filename, aux_path=aux_path))
                auxiliary_filepath = auxiliary_file_group.file(auxiliary_filename).get(dest=auxiliary_filepath)
            else:
                logging.info('++ Skipping fetch of auxiliary file {aux_path} because it already exists.'.format(aux_filename = auxiliary_filename, aux_path=aux_path))

            # Assemble a mapping of aux filenames to where they were saved
            fetched_auxiliary_files[auxiliary_filename] = auxiliary_filepath

        # Re-filter list of files for the ones the user wants to unzip
        matching_auxiliary_filenames = [
                auxiliary_filename for auxiliary_filename in matching_auxiliary_filenames
                if any([
                    fnmatch.fnmatch(auxiliary_filename, pattern) for pattern in aux_files_unzip_list
                ])
            ]

        # Loop over newly filtered list of auxiliary files and unzip them.
        logging.info('++ Unzipping {n} auxiliary files.'.format(n=len(matching_auxiliary_filenames)))
        for auxiliary_filename in matching_auxiliary_filenames:
            try:
                # Specify a subdirectory in which to place zip contents, using
                #   the base name of the zip file as the directory name.
                temp_unzip_path = os.path.join(aux_path, os.path.splitext(os.path.basename(auxiliary_filename))[0])
                if not os.path.exists(temp_unzip_path):
                    logging.info('++ Unzipping auxiliary file to {temp_unzip_path}.'.format(temp_unzip_path=temp_unzip_path))
                    # Prepare to unzip aux file
                    fzip = zipfile.ZipFile(fetched_auxiliary_files[auxiliary_filename], 'r')
                    # Attempt to unzip file into subdirectory of base subject path
                    fzip.extractall(path=temp_unzip_path)
                    fzip.close()
                    # If unzipping appears to be successful, remove zip file
                    os.remove(fetched_auxiliary_files[auxiliary_filename])
                else:
                    logging.info('++ Skipping unzip of auxiliary file to {temp_unzip_path} because that path already exists.'.format(temp_unzip_path=temp_unzip_path))
            except:
                logging.critical('++ WARNING: Failed to unzip auxiliary file {aux_file}.'.format(aux_file=auxiliary_filename))
                traceback.print_exc()

        logging.info('++ Attempting to organize any files matching pattern {regex} into a scan folder...'.format(regex=aux_files_org_regex))
        # Assemble a full list of all auxiliary files
        all_auxiliary_paths = [os.path.join(dp, f) for dp, dn, filenames in os.walk(aux_path) for f in filenames]
        # Loop over all auxiliary files and attempt to organize them if they match the regex.
        org_count = 0
        org_fail = 0
        non_org_count = 0
        for auxiliary_path in all_auxiliary_paths:
            base_name = os.path.basename(auxiliary_path)
            m = re.search(aux_files_org_regex, base_name)
            if m:
                # This file matched the organize regex! Get the scan name.
                scan_name = m[1]
                # Construct the putative scan path
                scan_path = os.path.join(sub_path, scan_name)
                try:
                    # Scan path probably already exists, but in case it doesn't create it.
                    os.mkdir(scan_path)
                    logging.info('Created new scan {scan_num} to accomodate auxiliary files.'.format(scan_num=scan_name))
                except FileExistsError:
                    pass

                # Yay, scan exists. Construct the destination path
                new_aux_path = os.path.join(scan_path, base_name)
                if retain_unorganized_aux_files:
                    # Copy, don't move
                    try:
                        shutil.copy(auxiliary_path, new_aux_path)
                        org_count = org_count + 1
                    except:
                        logging.critical('Failed to copy auxiliary file. src={src}, dst={dst}'.format(src=auxiliary_path, dst=new_aux_path))
                        traceback.print_exc()
                        org_fail = org_fail + 1
                else:
                    # Move, don't copy
                    try:
                        shutil.move(auxiliary_path, new_aux_path)
                        org_count = org_count + 1
                    except:
                        logging.critical('Failed to move auxiliary file. src={src}, dst={dst}'.format(src=auxiliary_path, dst=new_aux_path))
                        traceback.print_exc()
                        org_fail = org_fail + 1
            else:
                non_org_count = non_org_count + 1
        logging.info('++ Done organizing auxiliary files into scan folders:')
        logging.info('++    Successfully organized {n} auxiliary files into scan folders.'.format(n=org_count))
        logging.info('++    Failed to organize {n} auxiliary files into scan folders.'.format(n=org_fail))
        logging.info('++    {n} auxiliary files were not marked with a scan.'.format(n=non_org_count))

def pull_data(xnat, target_dir,
              project=None, sub_list=None,
              series_keep_list=[], series_skip_list=[],
              start=None, end=None, aux_files_fetch_list=['E*.zip', 'P*.zip'],
              aux_files_unzip_list=['E*.zip'], aux_files_org_regex='_scan_([0-9]+)',
              retain_unorganized_aux_files=True, aux_file_group_label='auxiliaryfiles',
              verbose=0, BIDS=False, skip_existing=True):
    """
    Grabs all relevant project data from HD-HNI XNAT instance

    Parameters
    -----------
    xnat : pyxnat.Interface
    target_dir : str
        Where data will be downloaded to
    project : str
        Project from which to pull data
    sub_list : str (filepath)
        Specifies subjects for whom to pull data
    series_keep_list : list of str
        A list specifying which series to pull down (i.e., PCASL, PASL, FLAIR)
    series_skip_list : lsit of str
        A list specifying which series NOT to pull down. This is ignored if
        series_keep_list is specified.
    start : datetime.datetime
        Only download data AFTER this date
    end : datetime.datetime
        Only download date BEFORE this date
    aux_file_group_fetch_list : list of str
        A list of filenames (wildcards allowed) to match experiment-related
            auxiliary resource files to fetch from the server.
    aux_file_group_org_list : list of str
        A list of filenames (wildcards allowed) to match experiment-related
            auxiliary resource files to organize into scan directories using.
            Files matching this list will be assumed to be
    aux_files_org_regex : str
        A regular expression with a single capturing group that extracts the
            scan ID from the auxiliary file name. If any auxiliary file matches
            the regex, it will be copied or moved to the scan folder identified
            by the extracted scan ID, depending on the value of
            retain_unorganized_aux_files
    retain_unorganized_aux_files : bool
        A boolean flag indicating whether or not to keep the original
            unorganized auxiliary files in place when organizing them. True
            indicates we retain the originals (copy), False indicates we do not
            (move).
    aux_file_group_label : str
        The XNAT label for the resource containing the experiment auxiliary
            files. Default is 'auxiliaryfiles'
    verbose : int
        Determines verbosity of printed progress statements
    BIDS : bool
        If downloaded data should be organized into BIDS format

    Returns
    -------
    list : list of subject directory paths
    """

    # Obtain project object
    proj = xnat.select.project(project)
    # Obtain list of available subject IDs
    subjects = proj.subjects().get()

    logging.debug('Found {n} subjects in this project:'.format(n=len(subjects)))
    for s in subjects:
        logging.debug(' - {sname}'.format(sname=proj.subject(s).label()))

    # Filter available subject list based on user supplied subject list
    subjects = [s for s in subjects if
                ((proj.subject(s).label() in sub_list) or (s in sub_list))]
    subjects = list(match_subject_dates(proj,subjects,start=start,end=end))

    # Warn user that no available subjects matched their list
    if len(subjects) == 0:
        logging.warning("No subjects found that match criteria - please check that you've specified valid subjects.")

    # if all_data < 1: series_skip_list.extend(['ASSET calibration', '3-Plane-Loc'])
    # if all_data < 2: series_skip_list.extend(['DICOM', 'SNAPSHOTS'])

    logging.info('Sub list:')
    logging.info(sub_list)
    logging.info('Ignored list:')
    logging.info(series_skip_list)
    logging.info('keep list:')
    logging.info(series_keep_list)

    subject_dirs = []

    # Loop over subject IDs
    logging.info('+++ Looking for data in {n} subjects...'.format(n=len(subjects)))
    for s in sorted(subjects):
        # Obtain subject object
        sub = proj.subject(s)
        logging.info('++ Getting data for subject {0}'.format(sub.label()))

        # Create directory for subject's data
        sub_path = os.path.join(target_dir,sub.label())
        try:
            os.mkdir(sub_path)
        except FileExistsError:
            logging.warning('++ Folder for this subject already exists.')

        # Obtain 1st (and probably only) experiment object in subject
        try: exp = sub.experiment(sub.experiments().get()[0])
        except IndexError:
            logging.info("++ WARNING: Subject data does not exist? Skipping.")
            continue

        # Warn user if there was more than one experiment for this subject
        if len(sub.experiments().get()) > 1:
            logging.critical('++ WARNING: Subject has more than one ' +
                'experiment, but at present this script is only designed ' +
                'to fetch data for one experiment per subject. Selecting ' +
                'only the first experiment for this subject.')

        # Loop over scan IDs
        for scanName in sorted(exp.scans().get(), key=int):
            logging.info(' ');
            logging.info('+  Getting scan #{scan}'.format(scan=scanName))

            # Obtain scan object
            scan = exp.scan(scanName)

            # Obtain series type/description
            try: s_descrip = scan.attrs.get('series_description')
            except: s_descrip = 'FAIL'
            logging.info('Preparing to load {s_descrip}'.format(s_descrip=s_descrip))

            # # Determine whether or not the user wants this series type
            # if is_keeper(s_descrip, series_keep_list=series_keep_list, series_skip_list=series_skip_list):
            #     logging.info('Fetching scan with series description {s_descrip}'.format(s_descrip=s_descrip))
            # else:
            #     logging.info('Skipping scan with series description {s_descrip}'.format(s_descrip=s_descrip))
            #     continue

            # Create folder for scan data
            scan_path = os.path.join(sub_path,scanName)
            try:
                os.mkdir(scan_path)
            except FileExistsError:
                logging.warning('+ Folder for scan #{scan} already exists.'.format(scan=scanName))
                if skip_existing:
                    logging.warning('+ Skipping fetch of scan that already exists.')
                    continue
                else:
                    logging.warning('+ Re-fetching scan that already exists.')

            logging.info('+  Scan {0}, {1}'.format(scanName,s_descrip))

            # Loop over resources within scan (a resource is a grouping of files)
            for resName in scan.resources().get():
                res = scan.resource(resName)

                # This is that BIDS thing that we don't use ¯\_(ツ)_/¯
                if BIDS and res.label() == 'DICOM':
                    f = res.files().get()[0]
                    res.file(f).get(os.path.join(scan_path,f))

                # Make sure the files within this resource are ones the user
                #   wants. Not sure why we do this twice, once for the scan,
                #   and once for each of the resources within the scan.
                if is_keeper(res.label(), series_keep_list, series_skip_list):
                    logging.info('Fetching resource with series description {s_descrip}'.format(s_descrip=res.label()))
                else:
                    logging.info('Skipping resource with series description {s_descrip}'.format(s_descrip=res.label()))
                    continue

                # Fetch all scan files in zip archive
                extracted_paths = res.get(scan_path, extract=True)
                logging.info('Fetched and extracted {n} files.'.format(n=len(extracted_paths)))
                extracted_root = os.path.dirname(extracted_paths[0])
                extracted_files = os.listdir(extracted_root)

                # Move unzipped files into base scan directory
                logging.info('Attempting to move unzipped files from temporary directroy to scan directory.')
                for file_name in extracted_files:
                    try:
                        shutil.move(os.path.join(extracted_root, file_name), scan_path)
                    except shutil.Error:
                        logging.critical('Filename collision: Could not move extracted file "{file_name}" to scan dir "{scan_path}", probably because it already existed there.'.format(file_name=file_name, scan_path=scan_path))

                # If all zipped files were moved to base scan directory, remove the temporary directory. If not, warn the user, and change the temporary directory name to "collisions"
                remaining_extracted_files = os.listdir(extracted_root)
                if len(remaining_extracted_files) == 0:
                    logging.info('Successfully moved all extracted files to scan directory. Removing temporary folder.')
                    os.rmdir(extracted_root)
                else:
                    collision_dir = os.path.join(scan_dir, 'collisions')
                    logging.critical('Could not move {n} files to scan directory. They will continue to exist in subdirectory {collision_dir}.')
                    num = 0
                    while os.path.exists(collision_dir):
                        collision_dir = os.path.join(scan_dir, 'collisions_{num}'.format(num=num))
                        num = num + 1
                    os.rename(extracted_root, collision_dir)

                # This was the old way - fetch each file one at a time. It took
                #   forever, so now we download the whole resource as a zip file
                # for f in sorted(res.files().get()):
                #     f_path = os.path.join(scan_path, f)
                #     logging.debug(' '*3 + os.path.join(sub.label(),scanName,f))
                #     if not os.path.exists(f_path):
                #         try:
                #             logging.info('Fetching file {f}...'.format(f=f))
                #             res.file(f).get(f_path)
                #         except:
                #             logging.warning('   Fetch error, skipping file {f}.'.format(f=f))
                #     else:
                #         logging.info('Skipping fetch of file {f} because it already exists.'.format(f=f))

        # Fetch and organize any requested auxiliary experiment files. If they
        #   match the provided regex, they will be organized into the scan
        #   folders
        fetch_and_organize_aux_files(exp=exp, sub_path=sub_path,
            aux_file_group_label=aux_file_group_label,
            aux_files_fetch_list=aux_files_fetch_list,
            aux_files_unzip_list=aux_files_unzip_list,
            aux_files_org_regex=aux_files_org_regex,
            retain_unorganized_aux_files=retain_unorganized_aux_files)



        # Keep a running log of the list of subject directories for later
        subject_dirs.append(sub_path)
        logging.info('\n')

    return subject_dirs


def match_subject_dates(project, subjects, start=None, end=None):
    """
    Parameters
    ----------
    project : pyxnat.core.resources.Project
    subjects : list
        Subjects to be downloaded (specified by sub_list)
    start : datetime.datetime
        Limit subjects to those scanned after this date
    end : datetime.datetime
        Limit subjects to those scanned before this date

    Yields
    -------
    subjects that match date specifications
    """

    if start is None: start = '0001-01-01'
    if end is None: end = datetime.datetime.now().isoformat()

    start = dateutil.parser.parse(start)
    end = dateutil.parser.parse(end)

    for s in subjects:
        sub = project.subject(s)
        try: exp = sub.experiment(sub.experiments().get()[0])
        except IndexError: continue
        date = dateutil.parser.parse(exp.attrs.get('date'))
        if date >= start and date < end: yield s

def load_list(fname, alt=[], wildcard=False):
    """
    Attempts to load `fname` into a list

    Parameters
    ----------
    fname : str
        relative or full path to file to be loaded (should be 1 dimensional)
    alt : list
        if fname fails to load, this will be used instead
    wildcard : bool
        whether to add wildcards to list elements for ease in regex matching

    Returns
    -------
    list
    """

    if fname is not None:
        try:
            with open(fname, 'r') as f:
                txt = f.read()
            loaded_list = txt.strip().split('\n')
            loaded_list = [el.strip() for el in loaded_list if len(el.strip()) > 0]
        except:
            loaded_list = alt[:]
    else:
        loaded_list = alt[:]

    if wildcard:
        loaded_list = wildcard_it(loaded_list)

    return loaded_list

    # if fname is not None:
    #     try:
    #         l = np.atleast_1d(np.genfromtxt(fname,delimiter=',',dtype='str'))
    #         l = l.tolist()
    #     except:
    #         l = alt
    #     if wildcard: l = wildcard_it(l)
    # else:
    #     l = alt
    #
    # return l[:]

def wildcard_it(descrip):
    """
    Adds flanking wildcards to every item in descrip

    Parameters
    ----------
    descrip : str or list

    Returns
    -------
    str or list : wildcards pre/appended
    """

    if isinstance(descrip,list):
        descrip = descrip[:]
        for n, s in enumerate(descrip): descrip[n] = '*' + s + '*'
    else: descrip = ['*' + descrip + '*']

    return descrip

def check_for_file(fname):
    """
    Checks to see if a file exists as specified or in pwd

    Parameters
    ----------
    fname : str
        relative or full path to file

    Returns
    -------
    str : relative or full path to file
    """

    if fname is not None and not os.path.exists(fname):
        call_path = os.getcwd()
        try_path = os.path.join(call_path,fname)
        if os.path.exists(try_path):
            return try_path
        else:
            script_path = os.path.dirname(os.path.abspath(__file__))
            try_path = os.path.join(script_path,fname)
            if os.path.exists(try_path):
                return try_path
            else:
                raise IOError('Cannot find {0}.'.format(fname) +
                              'Please make sure the file exists.')

    return fname

def get_subject_selection_list(sub_list=None, sub_file=None):
    if sub_list is not None:
        sub_list = parse_comma_separated_list(sub_list)
    else:
        sub_list = []

    sub_file = check_for_file(sub_file)
    if sub_file is not None:
        sub_list.extend(load_list(sub_file))
    return sub_list

def get_series_selection_lists(include_file=None, include_list=None, exclude_file=None, exclude_list=None):
    """
    Prepares lists of series to include or exclude

    Parameters
    ----------
    include_file : str or None
        Path to a file containing a list of series to include, one per line.
    exclude_file : str or None
        Path to a file containing a list of series to exclude, one per line.
    include_list : str or None
        Comma-separated string representing a list of series to include,
        one per line.
    exclude_list : str or None
        Comma-separated string representing a list of series to exclude,
        one per line.

    Returns
    -------
    dict : dict
        A dict containing series_keep_list and series_skip_list, each a list
        of series to either keep or exclude.
    """
    # if someone specifies include, ignored exclude
    if include_file is not None or include_list is not None:
        if exclude_list is not None or exclude_file is not None:
            logging.warning('Both excluded and included series types have been specified - in this circumstance exclude list is ignored.')
            exclude_file = None
            exclude_list = None

    # Parse include and exclude lists
    if include_list is not None:
        include_list = parse_comma_separated_list(include_list)
        logging.info('Include list parsed to be: {include_list}'.format(include_list=include_list))
    if exclude_list is not None:
        exclude_list = parse_comma_separated_list(exclude_list)
        logging.info('Exclude list parsed to be: {exclude_list}'.format(exclude_list=exclude_list))

    series_keep_list = []
    series_skip_list = []
    # Assemble list of series to include or exclude
    if include_file is not None:
        include_file = check_for_file(include_file)
        series_keep_list.extend(load_list(include_file))
    if include_list is not None:
        series_keep_list.extend(include_list)
    if exclude_file is not None:
        exclude_file = check_for_file(exclude_file)
        series_skip_list.extend(load_list(exclude_list))
    if exclude_list is not None:
        series_skip_list.extend(exclude_list)

    return dict(series_keep_list=series_keep_list, series_skip_list=series_skip_list)

def parse_comma_separated_list(cslist):
    """
    Parses a string containing a comma-separate list of parameters.

    Parameters
    ----------
    cslist : str
        A string containing a comma-separate list of parameters

    Returns
    -------
    list : a list of parameters
    """
    return [el.strip() for el in cslist.split(',') if len(el.strip()) > 0]

def establish_xnat_interface(user=None, host=None, port=None, path=None, password=None):
    """
    Attempts to establish an open connection with an XNAT server

    Parameters
    ----------
    user : str
        A valid username on the XNAT server
    host : str
        The hostname or IP address of the XNAT server
    port : int or str
        The port number of the XNAT server
    path : str
        The URL path of the XNAT server root, beginning with a slash (eg. "/xnat")

    Returns
    -------
    xnat : a pyxnat.Interface instance if the connection was successful, or the
        value None if not.
    """

    # Process default parameters
    if user is None: user = os.environ['USER']
    if host is None: host = DEFAULT_XNAT_HOST
    if port is None: port = DEFAULT_XNAT_PORT
    if path is None: path = DEFAULT_XNAT_PATH

    # Assemble full XNAT server root address from parts
    fullAddress = 'http://{host}:{port}{path}'.format(
        host=host,
        port=port,
        path=path)

    logging.info("Attempting to connect to xnat server at {user}@{fullAddress}".format(user=user, fullAddress=fullAddress))

    # Attempt to open a connection with the XNAT server,
    #   in the form of an Interface object.
    # If password is not supplied as a function argument,
    #   it is requested in the command line.
    #   Gives someone 5 attempts to get their password correct
    #   checks if the connection succeeded by getting XNAT
    #   projects; if no projects, then password is wrong.
    #   boots them after 5 attempts because seriously???
    # If the password is supplied as a function argument,
    #   the script will only try to connect once.
    logging.info('Attempting to log in with user {user}'.format(user=user))
    attempts = 0
    while True:
        xnat = Interface(server=fullAddress,
                         user=user, password=password)
        # xnat = Interface(server='https://hd-hni-xnat.cac.cornell.edu:8443/xnat',
        #                  user=params['user'],
        #                  cachedir='/tmp')
        p = xnat.select.projects().fetchall()
        if password is not None and len(p) == 0:
            logging.critical("Connection failed. Check parameters and try again.")
            return None
        if len(p) == 0 and attempts < 5:
            logging.critical("Incorrect password, please try again.")
            attempts += 1
        elif len(p) == 0 and attempts >= 5:
            logging.critical("Failed password too many times. Re-run this script to try again.")
            return None
        else: break

    logging.info("Login successful.");
    return xnat

def get_data(user, project, host=DEFAULT_XNAT_HOST, port=DEFAULT_XNAT_PORT,
    path=DEFAULT_XNAT_PATH, sub_list=None, sub_file=None, include_list=None,
    exclude_list=None, include_file=None, exclude_file=None, verbose=0,
    BIDS=False, **kwargs):
    """
    Prepares parameters and calls pull_data to get data from xnat server

    Parameters
    ----------
    kwargs : remaining keyword arguments to pass to pull_data

    Returns
    -------
    list : list of subject directory paths with fetched data
    """

    # Set up logging according to desired verbosity level.
    logging.getLogger().setLevel(VERBOSITY.get(verbose, logging.debug))

    # Check to see if input files exist somewhere
    sub_list = get_subject_selection_list(sub_list=sub_list, sub_file=sub_file)

    ssl = get_series_selection_lists(include_file=include_file, include_list=include_list, exclude_file=exclude_file, exclude_list=exclude_list)
    series_keep_list = ssl['series_keep_list']
    series_skip_list = ssl['series_skip_list']

    # Establish connection to XNAT server
    xnat = establish_xnat_interface(user=user, host=host, port=port, path=path)

    # Create target directory
    target_dir = os.path.join(os.getcwd(), '{0}_data'.format(project))
    if not os.path.exists(target_dir):
        os.mkdir(target_dir)

    # Get the data
    msg = 'Downloading data from XNAT'
    logging.info('{0}\n{1:^80}\n{2}'.format('='*80,msg,'='*80))
    subject_dirs = pull_data(xnat, target_dir, project=project,
                            sub_list=sub_list,
                            series_skip_list=series_skip_list,
                            series_keep_list=series_keep_list,
                            verbose=verbose, BIDS=BIDS, **kwargs)

    # BIDSify the data ??
    if BIDS:
        from cmrifxnat import Study

        curr_study = Study(target_dir)
        msg = 'BIDS process about to begin; this will take a little while.'
        logging.warning(msg)
        curr_study.bidsify(True if verbose > 1 else False)

    # Disconnect from XNAT and let user know everything is good to go.
    xnat.disconnect()
    msg = 'DONE'
    logging.info('{0}\n{1:^80}\n{2}'.format('='*80,msg,'='*80))
    return subject_dirs

if __name__ == "__main__":
    # This code funs only if this module is run directly, rather than imported
    #   by another function.
    parser = argparse.ArgumentParser(description='Download data from HD-HNI ' +
                                     'XNAT instance.')

    parser.add_argument('project',
                        help='Name of XNAT project to download data from.'    )
    parser.add_argument('-u',dest='user',required=False,
                        help='Username for XNAT access (password will be '    +
                        'requested via command line). Default is the user '   +
                        'you are signed in as on the local server where '     +
                        'this command is being run.',
                        default=DEFAULT_USER                                  )
    parser.add_argument('-x',dest='xnat_host',required=False,
                        help='IP address or hostname of XNAT server. Do not ' +
                        'include port or any other parts of the address '     +
                        'here. Default is \'' + DEFAULT_XNAT_HOST + '\'',
                        default=DEFAULT_XNAT_HOST                             )
    parser.add_argument('-p',dest='xnat_port',required=False,
                        help='Port for communicating with xnat server. '      +
                        'Default is \'' + DEFAULT_XNAT_PORT + '\'',
                        default=DEFAULT_XNAT_PORT                             )
    parser.add_argument('-t',dest='xnat_path',required=False,
                        help='URL path for xnat server. Default is \''        +
                        DEFAULT_XNAT_PATH + '\'', default=DEFAULT_XNAT_PATH   )
    # parser.add_argument('-a',dest='all_data',action='count',default=0,
    #                     help='Pull data for every scan, including '           +
    #                     'calibrations and localizers. Increase number of '    +
    #                     'a\'s (e.g., -aa) to pull more data. NOTE: this '     +
    #                     'will dramatically slow down program.'                )
    parser.add_argument('-v',dest='verbose',action='count',default=0,
                        help='Print occasional log messages to command line.' +
                        ' Increase number of v\'s to increase number of'      +
                        ' messages.'                                          )
    parser.add_argument('-s',dest='start',metavar='YYYY-MM-DD',default=None,
                        help='Start date. Will only download data for '       +
                        'subjects who were scanned after this date. Only ISO '+
                        '8601 format will be acknowledged (YYYY-MM-DD). Can ' +
                        'be used in conjunction with -e to specify a date '   +
                        'range.'                                              )
    parser.add_argument('-e',dest='end',metavar='YYYY-MM-DD',default=None,
                        help='End date. Will only download data for subjects '+
                        'who were scanned before this date. Only ISO 8601 '   +
                        'format will be acknowledged (YYYY-MM-DD). Can be '   +
                        'used in conjunction with -s to specify a date range.')
    parser.add_argument('--sub-list', dest='sub_list', metavar='file',
                        default=None, help='Text file specifying subjects to '+
                        'get data for. Default: pull all subjects'            )
    parser.add_argument('--include-file', dest='include_file', metavar='file',
                        default=None, help='Text file specifying series '     +
                        'description for data to download. Default: download '+
                        'all data. Note that this option is cumulative with ' +
                        '--include-list.'                                     )
    parser.add_argument('--exclude-file', dest='exclude_file', metavar='file',
                        default=None, help='Text file specifying series '     +
                        'descriptions for data NOT to download. Default: '    +
                        'exclude nothing.  Note that if --include-list or '   +
                        '--include-file is specified, --exclude-file is '     +
                        'ignored. This option is cumulative with '            +
                        '--exclude-list.'                                     )
    parser.add_argument('--include-list', dest='include_list', metavar='list',
                        default=None, help='Comma-separated list of series '  +
                        'descriptions for data to download. Example: '        +
                        'DICOM,BRIK '                                         +
                        'Default: download all data. Note that this option '  +
                        'is cumulative with --include-file')
    parser.add_argument('--exclude-list', dest='exclude_list', metavar='list',
                        default=None, help='Comma-separated list of series '  +
                        'descriptions for data NOT to download. Default: '    +
                        'exclude nothing.  Note that if --include-list or '   +
                        '--include-file is specified, --exclude-list and '    +
                        '--exclude-fileare ignored. This option is '          +
                        'cumulative with --exclude-file.'  )
    parser.add_argument('--aux-fetch-list', dest='aux_files_fetch_list',
                        metavar='list', default='E*.zip, P*.zip',
                        help='Comma-separated list of auxiliary files to '     +
                        'fetch. Wildcards are allowed. '                       +
                        'Default: "E*.zip, P*.zip"')
    parser.add_argument('--aux-unzip-list', dest='aux_files_unzip_list',
                        metavar='list', default='E*.zip',
                        help='Comma-separated list of auxiliary files to '     +
                        'unzip after fetching. Wildcards are allowed. '        +
                        'Default: "E*.zip"')
    parser.add_argument('--aux-org-regex', dest='aux_files_org_regex',
                        metavar='regex', default='scan_([0-9]+)',
                        help='A regular expression with a single capturing '   +
                        'group that captures the scan ID from within an '      +
                        'auxiliary filename. If an auxiliary file matches, it '+
                        'will be moved or copied to the corresponding scan '   +
                        'folder, depending on the value of --retain-aux_orig. '+
                        'Default: "scan_([0-9]+)"')
    parser.add_argument('--retain-aux-orig',
                        dest='retain_unorganized_aux_files',
                        action='store_true',
                        default=True, help='When organizing auxiliary files '  +
                        'into scan folders, this flag indicates that the '     +
                        'files should be copied, not moved.')
    parser.add_argument('--aux-label', dest='aux_file_group_label',
                        metavar='str', default='auxiliaryfiles',
                        help='The resource label under which the auxiliary '   +
                        'files are stored on the XNAT server. Default: '       +
                        '"auxiliaryfiles".')
    parser.add_argument('--BIDS',action='store_true',default=False,
                        help='Organize data into BIDS format immediately '    +
                        'after download. THIS FEATURE IS IN BETA -- use at '  +
                        'your own risk! Default: off'                         )
    parser.add_argument('-k', dest='skip_existing', action='store_true',
                        default=True, help='Skip fetching scan folders that ' +
                        'already exist. Default: True'                        )
    params = vars(parser.parse_args())

    get_data(params['user'],
        params['project'],
        host=params['xnat_host'],
        port=params['xnat_port'],
        path=params['xnat_path'],
        sub_list=params['sub_list'],
        include_list=params['include_list'],
        exclude_list=params['exclude_list'],
        include_file=params['include_file'],
        exclude_file=params['exclude_file'],
        verbose=params['verbose'],
        BIDS=params['BIDS'],
        start=params['start'],
        end=params['end'],
        # all_data=params['all_data'],
        skip_existing=params['skip_existing'],
        aux_files_fetch_list=params['aux_files_fetch_list'],
        aux_files_unzip_list=params['aux_files_unzip_list'],
        aux_files_org_regex=params['aux_files_org_regex'],
        retain_unorganized_aux_files=params['retain_unorganized_aux_files'],
        aux_file_group_label=params['aux_file_group_label']
        )
