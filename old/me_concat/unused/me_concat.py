#!/usr/bin/env python
"""
This script gets a list of exams in /dicom which were created in the last 24
hours, excluding directories that were created in the last 10 mins with the
assumption that there is ongoing file transfer from the scanner console. The
script checks to see if the exam has already been concatenated. If not, the
script calls nii_mdir_sdcme on the multiecho scans for each collected exam (via
the `concatenate` function).

This script is called by cronjob every hour on the hour from 9a-11p.

Maintainer: rdm222@cornell.edu
"""

import os
import os.path as op
import time
from datetime import datetime
from utils import concatenate, find_scans, flush_it

DICOM_DIR = '/dicom'


def last_mod(exam):
    """
    Returns time since last modification of file

    Parameters
    ----------
    exam : str

    Returns
    -------
    float : time (in seconds)
    """

    # set initial modification time to base
    t_mod = 0

    # iterate through exam directory
    for dirpath, dirname, fname in os.walk(exam):
        for f in fname:
            # if mod time for given file is newer than last file, update t_mod
            mod = os.stat(os.path.join(dirpath,f)).st_ctime
            if mod > t_mod: t_mod = mod

    # return difference from current time to t_mod
    return time.time() - t_mod


def check_dir(exam):
    """
    Confirms exam abides by all conditions

    1. `exam` is a directory,
    2. `exam` is a digit (e.g., '1956')
    3. `exam` was last modified <24 hours and >10 minutes ago,
    4. `exam` does not have 'medata/.complete' file, and
    5. `exam` has multiecho scans

    Parameters
    ----------
    exam : str
        path to exam directory

    Returns
    -------
    bool : whether all conditions are met
    """

    is_dir = op.isdir(exam) and op.basename(exam).isdigit()
    if not is_dir: return is_dir

    mod_good = last_mod(exam) < 60*60*24 and last_mod(exam) > 10*60
    if not mod_good: return mod_good

    complete = op.exists(op.join(DICOM_DIR,exam,'medata','.complete'))
    if complete: return not complete

    me = len(list(find_scans(exam))) > 0

    return is_dir and mod_good and not complete and me


def main():
    """
    Concatenates multiecho scans of recent exams that meet criteria
    """

    # get list of exams in DICOM_DIR (/dicom) that meet criterion
    exams = sorted([d for d in os.listdir(DICOM_DIR) if
                    check_dir(op.join(DICOM_DIR,d))])
    if len(exams) == 0: return

    # print time, date, and exams to concatenate to log file
    t = datetime.strftime(datetime.fromtimestamp(time.time()),'%D %H:%M:%S')
    d = 'Exams to concatenate: {0}'.format(', '.join(exams))
    print('\n{}\n{:^80}\n{:^80}\n{}'.format('='*80,t,d,'='*80))

    # iterate through exams and call concatenate() (from utils.py)
    for sub in exams:
        t = datetime.strftime(datetime.fromtimestamp(time.time()),'%H:%M:%S')
        print('+  {0}  Exam: {1} +'.format(t, sub))
        flush_it('++ Concatenating scans')

        concatenate(op.join(DICOM_DIR,sub), interactive=False)


if __name__ == '__main__':
    main()
