#!/usr/bin/env python
"""
Usage:   utils.py -h
                  [-d directory]  # directory where exam lives
                  [-e echoes]     # number of echoes in multiecho scans
                  [-s scans]      # specific scans to be concatenated
                  exam

This script can be called from the command line to manually concatenate exams
with multiecho scans. Minimum use requires specifying the exam to be
concatenated; can optionally specify which directory the exam lives in, how
many echoes the multiecho scans of that exam should have, and which scans to
concatenate. Successful concatenation will

Maintainer: rdm222@cornell.edu
"""

import subprocess
import os
import os.path as op
import sys
import glob
import argparse
import pydicom as dicom


def flush_it(msg):
    """
    Writes and immediately flushes a message to stdout

    Mostly a helper function; otherwise print() messages will get held up in
    buffer and only output occasionally, which can be annoying especially when
    calling this from the command line.

    Parameters
    ----------
    msg : str
        message to be written
    """

    sys.stdout.write(msg)
    sys.stdout.flush()


def find_scans(exam):
    """
    Finds all multiecho scans for `exam`

    Iterates through subdirectories of provided exam and checks DICOM header
    info for each scan to determine if it is multiecho

    Parameters
    ----------
    exam : str
        path to exam directory

    Yields
    ------
    ME scans (#s)
    """

    for dirpath, dirnames, filenames in os.walk(exam,topdown=True):
        for dir_ in dirnames:
            # if not a digit, it's not a DICOM directory
            if not dir_.isdigit(): continue

            # get the first dicom in the directory
            files = glob.glob(op.join(dirpath,dir_,'*.dcm'))
            dcm_info = dicom.read_file(files[0],force=True)

            # check multiecho scan
            if dcm_info[0x0019, 0x109c].value == 'epiRTme':
                yield int(dir_)


def check_concat(exam, echoes=3):
    """
    Confirms concatenation of given exam was successful

    Iterates through list of ME scans for `exam` and checks that there are
    appropriate number of run??.e0?.nii files for provided scan. Looks for
    highest echo #, provided by `echoes` input. Only returns scans that
    should be concatenated

    Parameters
    ----------
    exam : str
        relative or full path to exam
    echoes : int
        how many echoes there should be for ME scans in `exam`

    Yields
    ------
    ME scans that are not concatenated
    """

    incomplete = list(check_dcms(exam))

    for f in find_scans(exam):
        echo = 'run{0}.e0{1}.nii'.format(str(f).zfill(2),str(echoes))
        if not op.exists(op.join(exam,'medata',echo)) and f not in incomplete:
            yield f


def check_dcms(exam, scans=[]):
    """
    Confirms that all DICOMS exist for a given ME scan

    This will determine if any scans are incomplete (e.g., stopped during
    scanning) and should not be concatenated.

    Parameters
    ----------
    exam : str
    scans : list
        Which scans to check from `exam`. (Default: all ME scans)

    Yields
    ------
    ME scans that are not complete (i.e., not all DICOMS exist)
    """

    if not isinstance(scans,list): scans = [scans]
    if len(scans) == 0: scans = sorted(list(find_scans(exam)))

    for f in scans:
        files = glob.glob(op.join(exam,'{}'.format(str(f).zfill(4)),'*dcm'))
        dcm_info = dicom.read_file(files[0],force=True)

        # get the number of slices and number of volumes to be collected
        slice_num = int(dcm_info[0x0020,0x1002].value)
        vol_num = int(dcm_info[0x0020,0x0105].value)

        # if there are not appropriate number of DICOM files based on
        # prescription (slice_num * vol_num), then scan was likely aborted
        # mid-session -- do not try to concatenate it!
        if vol_num * slice_num != len(files):
            yield f


def make_complete(exam, echoes=3, interactive=True):
    """
    Makes text file denoting if concatenation was failure/success

    Attempts to concatenate any scans that were not concatenated successfully;
    produces '.failed' or '.complete' file depending on concatenation status.
    Also makes '.incomplete' files for scans that are incomplete (i.e., missing
    DICOM files).

    Parameters
    ----------
    exam : str
    echoes : int
        how many echoes there should be for ME scans in `exam`
    interactive : bool
        whether this is being run from command line or called from a script
    """

    # if some scans were not concatenated for some reason, give it one last go
    missed = list(check_concat(exam, echoes=echoes))
    if len(missed) > 0:
        call_mdir(missed, quiet=True)
        missed = list(check_concat(exam, echoes=echoes))

    # if some scans were incomplete, print statement saying so
    incomplete = list(check_dcms(exam))
    if len(incomplete) > 0:
        msg = '{0}WARNING: Scan(s) {1} incomplete (i.e., missing DICOM files).'
        print(msg.format(' '*3 if not interactive else '', str(incomplete)))

    # if there are still missing scans, label '.failed'; else, '.complete'
    # incomplete scans are NOT counted as "missing"
    if len(missed) > 0:
        name = '.failed'
        msg = '{0}FATAL: Scan(s) {1} failed to concatenate correctly.'
        print(msg.format(' '*3 if not interactive else '', str(missed)))
    else:
        name = '.complete'

    # create file specifying whether concatenation was success or failed
    # also create files specifying if any runs are incomplete
    if op.exists(op.join(exam,'medata')):
        with open(op.join(exam,'medata',name),'w') as source: pass
        for f in incomplete:
            temp = '.incomplete_run{0}'.format(str(f).zfill(2))
            with open(op.join(exam,'medata',temp),'w') as source: pass


def call_mdir(scans, echoes=3, interactive=True, quiet=False):
    """
    Calls subprocess to concatenate ME scans in `scans`

    Assumes you are already in the appropriate exam directory! Please make
    sure you're already in the appropriate exam directory...

    Parameters
    ----------
    scans : list
        scan #s to be concatenated
    echoes : int
        how many echoes there should be for scans in `scans`
    interactive : bool
        whether this is being run from command line or called from a script
    quiet : bool
        whether to suppress output messages
    """

    if echoes == 2:
        SCRIPT = 'nii_mdir2_sdcme'
    elif echoes == 3:
        SCRIPT = 'nii_mdir_sdcme'
    else:
        # we only have command-line scripts for concatenting 2- and 3-echo scans
        raise ValueError("Echoes must be 2 or 3."

    FNULL = open(os.devnull, 'w')
    progress = ''

    # iterate through scans
    for f in scans:
        # print progress statement
        if interactive and not quiet:
            progress = 'Concatenating images for scan {}.'
            progress = '\b'*len(progress) + progress.format(str(f).zfill(2))
        elif not quiet: progress = '.'
        else: progress = ''
        flush_it(progress)

        # call concatenation script on each successive scan
        subprocess.call([SCRIPT, str(f), str(f)],
                        stdout=FNULL, stderr=subprocess.STDOUT)

    # close /dev/null redirect pipe
    FNULL.close()
    if interactive and not quiet: flush_it('\n')
    elif not quiet: flush_it('Done!\n')


def concatenate(exam, echoes=3, interactive=True, scans=[]):
    """
    Concatenates ME `scans` for `exam` into NIFTI format

    Iterates through list of `scans` for `exam` and calls nii_mdir_sdcme
    to convert DICOMs into NIFTI format. Output scans are placed in
    exam/medata

    Parameters
    ----------
    exam : str
    echoes : int
        How many echoes there should be for ME scans in `exam`
    interactive : bool
        Whether this is being run from command line or called from a script
    scans : list
        Which scans to concatenate from `exam`. (Default: all ME scans)
    """

    os.chdir(exam)

    if not isinstance(scans,list): scans = [scans]
    if len(scans) == 0: scans = sorted(list(find_scans(exam)))

    call_mdir(scans, echoes=echoes, interactive=interactive)
    make_complete(exam, echoes=echoes, interactive=interactive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Concatenate multiecho scans')
    parser.add_argument('exam', help='Exam ID.')
    parser.add_argument('-d','--directory',default='/dicom',metavar='dir',
                        help='Directory where exam lives. (Default: /dicom)')
    parser.add_argument('-e','--echoes',default=3,metavar='echoes',
                        help='Number of echoes in ME scans. (Default: 3)')
    parser.add_argument('-s','--scans',default=[],metavar='scans',
                        help='Which scans to concatenate. (Default: all)')
    parameters = vars(parser.parse_args())

    exam = op.join(parameters['directory'], parameters['exam'])

    if not os.path.exists(exam):
        raise IOError('{0} doesn\'t exist on the AFNIPC?'.format(exam))

    try:
        concatenate(exam,
                    echoes=parameters['echoes'],
                    scans=parameters['scans'])
    except:
        print('Failed to concatenate...')
