#SBATCH -n 4
#SBATCH -J meica_batch
#SBATCH -o sbatch-%j.out
#SBATCH -e sbatch-%j.err
#SBATCH --mail-user=ngc26@cornell.edu
#SBATCH --mail-type=ALL

## !/path/to/xnat/venv/python
##
## !/bin/bash -l

# This script is designed to
# 1. Pull MRI data from an XNAT server
# 2. Process the MRI data to transform DICOM files into multi-echo

# Todo
#   Finish implementing multiecho DICOM deletion after successful concatenation
#   Make script automatically skip multiecho concatenation if appropriate nifti files already exist
#   Possibly pull data from XNAT in parallel?
#   Possibly make this play nicely with SLURM
#   Add ability to specify data output directory, so it doesn't always dump to the cwd
#   Create executable wrapper? Could activate xnat environment then run
#   Unify/normalize formatting of log output
#   Make bigger formatting divisions in output between major steps in the process

import os
from get_xnat_data import get_data
from me_concat.concatenate_multiecho import concatenate_subject
import argparse
import sys
import logging

def main():
    # Parse command line arguments
    params = parseArgs()

    VERBOSITY = {0 : logging.CRITICAL,
                 1 : logging.WARNING,
                 2 : logging.INFO,
                 3 : logging.DEBUG}
    # set logging level and turn off annoying urrllib3 error
    logging.basicConfig(level=VERBOSITY.get(params['verbose'], logging.DEBUG),
                        format='%(message)s')
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.INFO)

    logging.info("Starting XNAT MRI data pull & multi-echo preprocess job: ")
    logging.debug("Location of python:")
    logging.debug(sys.executable)

    # Print info about SLURM environment
    print_slurm_info()

    # Step 1: Get DICOM and other files from XNAT server
    logging.info('Fetching data from xnat server')
    subject_dir_list = get_data(params['user'],
                                params['project'],
                                host=params['xnat_host'],
                                port=params['xnat_port'],
                                path=params['xnat_path'],
                                sub_list=params['sub_list'],
                                sub_file=params['sub_file'],
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

    # Look through each subject dir and concatenate dicom files in each scan within,
    #   taking advantage of SLURM batch processing if available
    for subject_dir in subject_dir_list:
        logging.info('Concatentating scans within:')
        logging.info(subject_dir)
        concatenate_subject(subject_dir, echoes=3, delete_dcms=params['delete_dcms'])

def parseArgs():
    DEFAULT_XNAT_HOST = 'fh-mi-cmrifserv.human.cornell.edu'
    DEFAULT_XNAT_PORT = '8080'
    DEFAULT_XNAT_PATH = '/xnat'
    DEFAULT_USER = os.environ['USER']

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
    parser.add_argument('--host',dest='xnat_host',required=False,
                        help='IP address or hostname of XNAT server. Do not ' +
                        'include port or any other parts of the address '     +
                        'here. Default is \'' + DEFAULT_XNAT_HOST + '\'',
                        default=DEFAULT_XNAT_HOST                             )
    parser.add_argument('--port',dest='xnat_port',required=False,
                        help='Port for communicating with xnat server. '      +
                        'Default is \'' + DEFAULT_XNAT_PORT + '\'',
                        default=DEFAULT_XNAT_PORT                             )
    parser.add_argument('--path',dest='xnat_path',required=False,
                        help='URL path for xnat server. Default is \''        +
                        DEFAULT_XNAT_PATH + '\'', default=DEFAULT_XNAT_PATH   )
    # parser.add_argument('-a',dest='all_data',action='count',default=0,
    #                     help='Pull data for every scan, including '           +
    #                     'calibrations and localizers. Increase number of '    +
    #                     'a\'s (e.g., -aa) to pull more data. NOTE: this '     +
    #                     'will dramatically slow down program.'                )
    parser.add_argument('-v', dest='verbose', action='count', default=0,
                        help='Print occasional log messages to command line.' +
                        ' Increase number of v\'s to increase number of'      +
                        ' messages.'                                          )
    parser.add_argument('-s', dest='start', metavar='YYYY-MM-DD', default=None,
                        help='Start date. Will only download data for '       +
                        'subjects who were scanned after this date. Only ISO '+
                        '8601 format will be acknowledged (YYYY-MM-DD). Can ' +
                        'be used in conjunction with -e to specify a date '   +
                        'range.'                                              )
    parser.add_argument('-e',dest='end', metavar='YYYY-MM-DD', default=None,
                        help='End date. Will only download data for subjects '+
                        'who were scanned before this date. Only ISO 8601 '   +
                        'format will be acknowledged (YYYY-MM-DD). Can be '   +
                        'used in conjunction with -s to specify a date range.')
    parser.add_argument('--sub-list', dest='sub_list', metavar='list',
                        default=None, help='Comma-separated list of subjects '+
                        'to get data for. Default: pull all subjects. Note '  +
                        'that this is cumulative with --sub-file. If '        +
                        '--sub-file and --sub-list are both omitted, ALL '    +
                        'subjects will be pulled'                             )
    parser.add_argument('--sub-file', dest='sub_file', metavar='file',
                        default=None, help='Text file specifying subjects to '+
                        'get data for. File should contain one subject per '  +
                        'line. Default: pull all subjects. Note that this is '+
                        ' cumulative with --sub-list.  If --sub-file and '    +
                        '--sub-list are both omitted, ALL subjects will be '  +
                        'pulled'                                              )
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
    parser.add_argument('-d', action='store_true', default=False,
                        dest='delete_dcms', help='Auto-delete downloaded '    +
                        'DICOM files after they have been combined into '     +
                        'multiecho nii files.'                                )
    parser.add_argument('-k', dest='skip_existing', action='store_true',
                        default=True, help='Skip fetching scan folders that ' +
                        'already exist. Default: True'                        )
    params = vars(parser.parse_args())
    return params

def print_slurm_info():
    # Print properties of job as submitted
    logging.info("SLURM_JOB_ID = {SLURM_JOB_ID}".format(SLURM_JOB_ID=os.getenv("SLURM_JOB_ID")))
    logging.info("SLURM_NTASKS = {SLURM_NTASKS}".format(SLURM_NTASKS=os.getenv("SLURM_NTASKS")))
    logging.info("SLURM_NTASKS_PER_NODE = {SLURM_NTASKS_PER_NODE}".format(SLURM_NTASKS_PER_NODE=os.getenv("SLURM_NTASKS_PER_NODE")))
    logging.info("SLURM_CPUS_PER_TASK = {SLURM_CPUS_PER_TASK}".format(SLURM_CPUS_PER_TASK=os.getenv("SLURM_CPUS_PER_TASK")))
    logging.info("SLURM_JOB_NUM_NODES = {SLURM_JOB_NUM_NODES}".format(SLURM_JOB_NUM_NODES=os.getenv("SLURM_JOB_NUM_NODES")))
    # Print properties of job as scheduled by Slurm
    logging.info("SLURM_JOB_NODELIST = {SLURM_JOB_NODELIST}".format(SLURM_JOB_NODELIST=os.getenv("SLURM_JOB_NODELIST")))
    logging.info("SLURM_TASKS_PER_NODE = {SLURM_TASKS_PER_NODE}".format(SLURM_TASKS_PER_NODE=os.getenv("SLURM_TASKS_PER_NODE")))
    logging.info("SLURM_JOB_CPUS_PER_NODE = {SLURM_JOB_CPUS_PER_NODE}".format(SLURM_JOB_CPUS_PER_NODE=os.getenv("SLURM_JOB_CPUS_PER_NODE")))
    logging.info("SLURM_CPUS_ON_NODE = {SLURM_CPUS_ON_NODE}".format(SLURM_CPUS_ON_NODE=os.getenv("SLURM_CPUS_ON_NODE")))

if __name__ == "__main__":
    main()
