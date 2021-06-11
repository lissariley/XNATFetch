#!/usr/bin/env python
"""
Usage:   concat_func.py -h
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
Updated by: bmk27@cornell.edu to be used on a Red Cloud instance instead of the old ??? server
"""
import traceback
import subprocess
import multiprocessing as mp
import os
import os.path as op
import sys
import glob
import argparse
import time
import re
import shutil
import logging
    # Older version of pydicom library used to import simply as "dicom"
try:
    import pydicom as dicom
except ImportError:
    logging.critical('Module not found. If you should be in a virtual environment, make sure it has been activated.')
    traceback.print_exc(file=sys.stdout)

# This must be the path to the nii_mdir script for 3-echo scans:
NII_MDIR_SCRIPT = 'concat_utils/nii_mdir_sdcme'
# This must be the path to the nii_mdir script for 2-echo scans:
NII_MDIR2_SCRIPT = 'concat_utils/nii_mdir2_sdcme'

# Code in DICOM header indicating it represents a multiecho scan.
ME_HEADER_CODE = 'epiRTme'

# Sub directory within each scan directory in which to place the
#   concatenated multiecho files
ME_SUBDIR = 'medata'

# def flush_it(msg):
#     """Writes and immediately flushes a message to stdout
#
#     Parameters
#     ----------
#     msg : str
#         Message to be written
#     """
#
#     sys.stdout.write(msg)
#     sys.stdout.flush()

def get_scan_dirs(exam_dir=None, scan_dirs=[], filter_scan_dirs=True):
    """Convenience function to handle user either passing a list of scan_dirs
    directly, or passing in an exam_dir in which to search for scans.

    Parameters
    ----------
    exam_dir : str (path)
        Path to the exam root directory. If not supplied, scan_dirs must be
        supplied.
    scan_dirs : list of str (paths)
        Which scan directories to check. If not supplied, exam_dirs must be
        supplied (all ME scans found within exam_dir will be used)
    filter_scan_dirs : bool
        Should directly passed scan_dirs be checked to see if they are
        multiecho? Default is True.

    Returns
    ------
    List of ME scan dirs
    """
    if not isinstance(scan_dirs, list):
        scan_dirs = [scan_dirs]
    if len(scan_dirs) == 0:
        # No list of scan_dirs passed
        if exam_dir is None:
            # Also no exam_dir was passed, this won't work.
            raise Exception('Either an exam_dir to search for scans, or a list of scan_dirs is required.')
        else:
            # Find scan_dirs within exam_dir
            scan_dirs = sorted(list(find_scans(exam_dir)))
    else:
        # List of scan_dirs was passed
        if filter_scan_dirs:
            # If we're filtering scan_dirs, do that now.
            scan_dirs = [scan_dir for scan_dir in scan_dirs if is_scan_ME(scan_dir)]

    return scan_dirs

def find_scans(exam_dir):
    """Finds all ME scans for `exam`

    Iterates through subdirectories of provided exam and checks
    DICOM header info for each scan to determine if it's multiecho

    Parameters
    ----------
    exam_dir : str (path)
        The exam directory potentially containing numbered scan directories

    Yields
    ------
    str : paths of ME scans
    """

    logging.info('Searching {dir} for multiecho DICOM files...\n'.format(dir=exam_dir))
    for dirpath, dirnames, filenames in os.walk(exam_dir, topdown=True):
        for dir_ in dirnames:
            # if not a digit, it's not a DICOM directory
            if not dir_.isdigit():
                logging.info('Skipping directory {dir} because it is not numbered, and therefore not a DICOM directory.'.format(dir=dir_))
                continue

            scan_dir = op.join(dirpath, dir_)

            logging.info('Found scan dir {scan}\n'.format(scan=scan_dir))

            if is_scan_ME(scan_dir):
                yield scan_dir

def is_scan_ME(scan_dir):
    """Checks if the given scan_dir represents a multi-echo scan

    Checks the DICOM header info for the first DICOM file in the scan to
    determine if it's a multiecho scan or not.

    Parameters
    ----------
    scan_dir : str (path)
        The scan directory containing DICOM files

    Returns
    ------
    bool : does this scan directory represent a multi echo scan?
    """
    files = glob.glob(op.join(scan_dir,'*.dcm'))
    if len(files) == 0:
        logging.info('No files found in scan dir {scan}\n'.format(scan=scan_dir))
        return False

    logging.info('Found {k} DICOM files in scan dir {scan}...\n'.format(scan=scan_dir, k=len(files)))

    # check if header info of first DICOM file in directory is indicative of a multiecho scan
    dcm_info = dicom.read_file(files[0], force=True)
    scan_is_ME = dcm_info[0x0019, 0x109c].value == ME_HEADER_CODE
    if scan_is_ME:
        logging.info('\t...and they appear to be multiecho files!\n')
    else:
        logging.info('\t...but based on the DICOM header info, they do not appear to be multiecho files.\n')
    return scan_is_ME

def find_incomplete_concatenations(exam_dir=None, scan_dirs=[], multiEchoSubDir=ME_SUBDIR, echoes=3):
    """Confirms concatenation of given exam was successful

    Iterates through list of ME scans for `exam` and checks that there are
    appropriate number of run??.e0?.nii files for provided scan. Looks for
    highest echo #, provided by `echoes` input. Only returns scans that
    should be concatenated

    Parameters
    ----------
    exam_dir : str (path)
        Path to the exam root directory. If not supplied, scan_dirs must be
        supplied.
    scan_dirs : list of str (paths)
        Which scan directories to check. If not supplied, exam_dirs must be
        supplied (all ME scans found within exam_dir will be used)
    echoes : int
        How many echoes there should be for ME scans in `exam_dir`

    Yields
    ------
    ME scans that are not concatenated
    """

    scan_dirs = get_scan_dirs(exam_dir=exam_dir, scan_dirs=scan_dirs)

    # Check list of
    incomplete_scan_dirs = list(find_incomplete_dicom_sets(exam_dir))

    for scan_dirs in find_scans(exam_dir):
        echo = 'run{0}.e0{1}.nii'.format(str(scan).zfill(2),str(echoes))
        if not op.exists(op.join(exam, multiEchoSubDir, echo)) and scan not in incomplete_scan_dirs:
            yield scan

def find_incomplete_dicom_sets(exam_dir=None, scan_dirs=[]):
    """Confirms that all DICOMS exist for a given ME scan

    This will determine if any scans are incomplete (e.g., stopped during
    scanning) and should not be concatenated.

    Parameters
    ----------
    exam_dir : str (path)
        Path to the exam root directory
    scan_dirs : list of str (paths)
        Which scan directories to check. (Default: search for all ME scans
        within exam_dir)

    Yields
    ------
    ME scan directories that are not complete (i.e., not all DICOMS exist)
    """

    scan_dirs = get_scan_dirs(exam_dir=exam_dir, scan_dirs=scan_dirs)

    for scan_dir in scan_dirs:
        files = glob.glob(op.join(scan_dir, '*dcm'))
        dcm_info = dicom.read_file(files[0],force=True)

        slice_num = int(dcm_info[0x0020,0x1002].value)
        vol_num = int(dcm_info[0x0020,0x0105].value)

        if vol_num * slice_num != len(files):
            yield scan

def make_complete(exam_dir, echoes=3, interactive=True, multiEchoSubDir=ME_SUBDIR):
    """Makes text file denoting if concatenation was failure/success

    Attempts to concatenate any scans that were not concatenated successfully;
    produces '.failed' or '.complete' file depending on concatenation status.
    Also makes '.incomplete' files for scans that are incomplete (i.e., missing
    DICOM files).

    Parameters
    ----------
    exam : str
    echoes : int
        How many echoes there should be for ME scans in `exam`
    interactive : bool
        Whether this is being run from command line or called from a script
    """

    # # if some scans were missed, give it one last go
    # missed = list(find_incomplete_concatenations(exam_dir, echoes=echoes))
    # if len(missed) > 0:
    #     call_mdir(missed, exam_dir, quiet=True)
    #     missed = list(find_incomplete_concatenations(exam_dir, echoes=echoes))

    # if some scans were incomplete, print statement saying so
    incomplete = list(find_incomplete_dicom_sets(exam_dir))
    if len(incomplete) > 0:
        logging.warning('WARNING: Scan(s) {incompletes} incomplete (i.e., missing DICOM files).'.format(incompletes = str(incomplete)))
    else:
        logging.info('No incomplete sets of dicom files detected!')

    # if there are still missing scans, label '.failed'; else, '.complete'
    missed = list(find_incomplete_concatenations(exam_dir, echoes=echoes))
    if len(missed) > 0:
        logging.critical('FATAL: Scan(s) {missed} failed to concatenate correctly.'.format(missed=str(missed)))
    else:
        logging.info('No missed scans!')

    # # create file specifying whether concatenation was success or failed
    # # also create files specifying if any runs are incomplete
    # if op.exists(op.join(exams_dir, exam, multiEchoSubDir)):
    #     with open(op.join(exams_dir, exam, multiEchoSubDir, name),'w') as source:
    #         pass
    #     for scan in incomplete:
    #         temp = '.incomplete_run{0}'.format(str(scan).zfill(2))
    #         with open(op.join(exams_dir, exam, multiEchoSubDir, temp),'w') as source:
    #             pass

def call_mdir(scans, exam_dir, echoes=3):
    """Calls subprocess to concatenate ME scans in `scans`

    Assumes you are already in the appropriate exam directory! Please make
    sure you're already in the appropriate exam directory...

    Parameters
    ----------
    scans : list
        Scan #s to be concatenated
    exam_dir : str (path)
        path
    echoes : int
        How many echoes there should be for scans in `scans`
    """

    concat_path = op.join(__file__, 'concat_utils')
    if echoes == 2:
        concat_script = NII_MDIR2_SCRIPT
    elif echoes == 3:
        concat_script = NII_MDIR_SCRIPT
    else:
        # we only have command-line scripts for concatenting 2- and 3-echo scans
        raise ValueError("Echoes must be 2 or 3.")

    FNULL = open(os.devnull, 'w')

    # iterate through scans
    for scan in scans:
        # print progress statement
        logging.info('Concatenating images for scan {scanNum}.'.format(scanNum = scan))
        logging.debug('\nCurrent __file__:\n')
        logging.debug(__file__+'\n')
        logging.debug('os.cwd = \n')
        logging.debug(os.getcwd()+'\n')

        # call concatenation script on each successive scan
        subprocess.Popen([concat_script, str(scan), str(scan)],
                        stdout=FNULL, stderr=subprocess.STDOUT)

    # close /dev/null redirect pipe
    FNULL.close()

    logging.info('Done!\n')

def concatenate_subject(subject_dir, echoes=3, delete_dcms=False):
    scan_dirs = get_scan_dirs(exam_dir=subject_dir)
    concatenate_scans(scan_dirs, echoes=echoes, delete_dcms=delete_dcms)

def concatenate_scans(scan_dirs, echoes=3, interactive=True, delete_dcms=False):
    for scan_dir in scan_dirs:
        concatenate_scan(scan_dir, echoes=echoes, interactive=interactive, delete_dcms=delete_dcms)
    logging.info("Finished concatenation!")
    logging.info("Checking for incomplete concatenations...")
    for scan_dir in scan_dirs:
        make_complete(scan_dir, echoes=echoes, interactive=interactive)
    logging.info("...done!")


def get_slice_index(dcm_file):
    return dicom.dcmread(dcm_file, specific_tags=[(0x0019,0x10a2)]).get((0x0019, 0x10a2)).value

def concatenate_scan(scan_dir, echoes=3, interactive=True, delete_dcms=False):
    """Concatenates ME `scans` for `exam` into NIFTI format

    Iterates through list of `scans` for `exam` and calls nii_mdir_sdcme
    to convert DICOMs into NIFTI format. Output scans are placed in
    exam/medata

    Parameters
    ----------
    scan_dir : str (path)
        Path to the scan directory containing multiecho DICOM files
    echoes : int
        How many echoes there should be for ME scans in `exam`
    interactive : bool
        Whether this is being run from command line or called from a script
    scans : list
        Which scans to concatenate from `exam`. (Default: all ME scans)
    delete_dcms : bool
        Whether to delete DICOM (.dcm) files after successful concatenation or
        not
    """

    logging.info('Concatenating scans...')
    logging.debug('scan_dir=', scan_dir)

    scan_name = op.basename(op.normpath(op.abspath(scan_dir)))

    me_dir = op.join(scan_dir, ME_SUBDIR)
    logging.debug('me_dir=', me_dir)
    try:
        os.mkdir(me_dir)
    except FileExistsError:
        logging.info('Multiecho directory {me_dir} already exists.\n'.format(me_dir=me_dir))

    # Get list of dicom files in scan_dir
    dicom_list = glob.glob(op.join(scan_dir,'*.dcm'))

    # Pass dicom files to the header parsing utility to get each file's slice
    #   index (aka "RawDataRunNumber"). Each slice index corresponds to one
    #   spatial slice position and one echo number. So, for example, index 3012
    #   might be the echo #2 nose-level slice. If the scan has 122 full brain
    #   "volumes", repeated 3 times each for the three echoes, and each brain
    #   volume consists of 40 spatial slices, then there would be 40 * 3 = 120
    #   unique slice indices, and each index will be repeated 122 times.
    logging.info('Extracting DICOM slice indices from headers...')
    t1 = time.time()
    with mp.Pool(16) as pool:
        index_list = pool.map(get_slice_index, dicom_list)

    logging.info('Elapsed time = {time}'.format(time=time.time()-t1))
    logging.info('...complete')

    logging.info('Arranging DICOM files for niftification...')

    # Make sure # of slices is divisible by 3
    if len(index_list) % echoes != 0:
        raise IndexError('Warning, # of dicom files (slices) ({nSlices}) is not divisible by the # of echoes ({nEchoes}). Something is wrong.'.format(nSlices=len(index_list), nEchoes=echoes))

    # Generate mapping of slice to dicom file paths. Each index corresponds to
    #   many dicom files.
    index_mapping = {}
    for file, index in zip(dicom_list, index_list):
        if index in index_mapping:
            index_mapping[index].append(file)
        else:
            index_mapping[index] = [file]

    # Prep file number extraction regex
    fileNumbering = re.compile('.*-([0-9]+)-[0-9a-zA-Z]+\.[Dd][Cc][Mm]$')
    fileNumberExtractor = lambda f:int(fileNumbering.match(f).group(1))

    # Sort files within each slice index by file number
    for index in index_mapping:
        index_mapping[index] = sorted(index_mapping[index], key=fileNumberExtractor)

    # Get the number of de-echoed slices
    nTotalSlices = len(index_list)                          # Number of slices
    nSpatialSlices = len(index_mapping) // echoes           # Number of unique space slices
    nSpaceTimeSlices = nTotalSlices // echoes               # Number of unique space-time slices
    nTimePoints = nTotalSlices // (echoes * nSpatialSlices) # Number of time slices

    slice_indices = sorted(index_mapping.keys())

    slice_indices_by_echo = [slice_indices[k:k + nSpatialSlices] for k in range(0, nSpatialSlices * echoes, nSpatialSlices)]

    concat_files = [None for e in range(echoes)]
    infile_lists = [None for e in range(echoes)]
    concat_file_list = [[['' for x in range(nSpatialSlices)] for t in range(nTimePoints)] for e in range(echoes)]
    for nEcho in range(echoes):
        for t in range(nTimePoints):
            for x in range(nSpatialSlices):
                index = slice_indices_by_echo[nEcho][x]
                file = index_mapping[index][t]
                concat_file_list[nEcho][t][x] = file
        concat_files[nEcho] = '\n'.join([' '.join([concat_file_list[nEcho][t][x] for x in range(nSpatialSlices)]) for t in range(nTimePoints)])
        infile_lists[nEcho] = op.join(me_dir, '_me{echo}_infilelist'.format(echo=nEcho))

    for nEcho in range(echoes):
        with open(infile_lists[nEcho], 'w') as f:
            f.write(concat_files[nEcho])

    logging.info('...complete')
    logging.info('In scan {scan}:'.format(scan=scan_dir))
    logging.info('We found...')
    logging.info('   ...{nTotalSlices} total slices'.format(nTotalSlices=nTotalSlices))
    logging.info('   ...{nSpatialSlices} spatial slices'.format(nSpatialSlices=nSpatialSlices))
    logging.info('   ...{nTimePoints} time points (times when full brain was scanned, not counting echoes separately)'.format(nTimePoints=nTimePoints))
    logging.info('   ...{nSpaceTimeSlices} space-time slices (unique spatial slice/time point combinations)'.format(nSpaceTimeSlices=nSpaceTimeSlices))
    logging.info('Running DIMON on each echo to produce a nifti file...')

    temp_dir_template = op.join(me_dir, 'temp_{echo}')

    # Call Dimon for each echo-group of dicoms, processing them into nifti files.
    dimon_proc = [None for nEcho in range(echoes)]
    for nEcho in range(echoes):
        logging.info('Processing echo #{k}/{n}...'.format(k=nEcho, n=echoes))
        # Format the output filename for the nifti files
        output_filename = 'run{scan_name:04d}.e{echo:02d}'.format(scan_name=int(scan_name), echo=nEcho)
        # Format the name for some of the temporary files
        gert_filename = 'GERT_Reco_dicom_{scan_name:03d}_e{echo:02d}'.format(scan_name=int(scan_name), echo=nEcho)
        # Create temp dir in which to run this Dimon process, so it doesn't
        #   interfere with the temp files created by other Dimon processes
        #   running in parallel.
        temp_dir = temp_dir_template.format(echo=nEcho)
        try:
            os.mkdir(temp_dir)
        except FileExistsError:
            pass
        # Set up the Dimon call
        command_list = ['Dimon', '-infile_list', infile_lists[nEcho], '-GERT_Reco', '-gert_filename', gert_filename, '-gert_create_dataset', '-gert_outdir', me_dir, '-gert_to3d_prefix', output_filename, '-gert_write_as_nifti', '-quit']

        # Start the Dimon process, using the temp_dir as the curent working
        #   directory.
        dimon_proc[nEcho] = subprocess.Popen(command_list, cwd=temp_dir, stdout=subprocess.PIPE)

    logging.debug('Current contents of me_dir:')
    logging.debug(os.listdir(me_dir))

    for nEcho in range(echoes):
        # Wait for each echo to be processed
        logging.info(dimon_proc[nEcho].communicate()[0])
        temp_dir = temp_dir_template.format(echo=nEcho)
        logging.debug('Removing temp directory:')
        logging.debug(temp_dir)
        shutil.rmtree(temp_dir)
        # temp_files = glob.glob(op.join(scan_dir, 'dimon.files.run.*'))
        # temp_files.extend(glob.glob(op.join(scan_dir, 'GERT_Reco_dicom_*')))
        # for temp_file in temp_files:
        #     print('Deleting temp file: {file}'.format(file=temp_file))
        #     os.remove(temp_file)
        logging.info('...done processing echo #{k}/{n}...'.format(k=nEcho, n=echoes))

    logging.info('...complete')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
                        description='Concatenate multiecho scans.')
    parser.add_argument('exam', help='Exam ID.')
    parser.add_argument('-d','--directory', default='/dicom', metavar='dir',
                        help='Directory where exam lives. (Default: /dicom)')
    parser.add_argument('-e','--echoes', default=3, metavar='echoes',
                        help='Number of echoes in ME scans. (Default: 3)')
    parser.add_argument('-s','--scans', default=[], metavar='scans',
                        help='Which scans to concatenate. (Default: all)')
    args, unknown = parser.parse_known_args()
    parameters = vars(args)

    exam = op.join(parameters['directory'], parameters['exam'])

    if not op.exists(exam):
        raise IOError('{0} doesn\'t exist on the AFNIPC?'.format(exam))

    try:
        concatenate(exam, echoes=parameters['echoes'],
                    scans=parameters['scans'])
    except:
        logging.critical('Failed to concatenate...')
