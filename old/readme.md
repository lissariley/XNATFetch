# Documentation for `/opt/xnat/get_data.py`
# Maintained by: rdm222@cornell.edu

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  IMPORTANT NOTE  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
If you are using this program on the HD-HNI server (as intended), you MUST
enter the following command before usage:

    $ module load python-2.7.6

If you do not enter this command BEFORE CALLING get_data.py, you WILL encounter
an error.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

If you have any questions about these instructions or encounter any problems
in using the program, send an e-mail to the address above ("Maintained by:")
with the command you entered, any relevant files that may have been included,
as well as the error output.

===============================================================================
                                     Usage
===============================================================================
get_data.py [-h, --help]        \
            [-a[a]]             \
            [-v[v[v]]]          \
            [-s YYYY-MM-DD]     \
            [-e YYYY-MM-DD]     \
            [--sublist file]    \
            [--include file]    \
            [--exclude file]    \
            [-u username]          \
            [-x server_address] \
            [-p server_port]    \
            [-t server_path]    \
            project

NOTE: All arguments in brackets [] are OPTIONAL. Arguments not in brackets are,
thus, REQUIRED.

===============================================================================
                                    Arguments
===============================================================================
-h¸ --help      Displays help information for get_data.py

-a[a]           Determines amount of data downloaded from XNAT. By default,
                this script avoids downloading DICOM files and skips
                localizer/calibration scans. Including one -a will download
                localizer/calibration scans, whereas -aa will download
                localizer/calibrations AND all DICOM files.

-v[v[v]]        Determines verbosity of messages output to screen. As you
                increase the number you will get more messages.

-s YYYY-MM-DD   If you specify option with a relevant date, only subjects who
                were scanned after that date will be downloaded. Please use
                ISO 8601 format (i.e., what is specified). You can use this in
                conjunction with [-e] to specify a date range to pull from! If
                you do not specify [-e], then you will get all subjects who
                were scanned starting with the specified date until the
                current time.

-e YYYY-MM-DD   If you specify option with a relevant date, only subjects who
                were scanned before that date will be downloaded. Please use
                ISO 8601 format (i.e., what is specified). You can use this in
                conjunction with [-s] to specify a date range to pull from! If
                you do not specify [-s], then you will get all subjects who
                were scanned before the specified date until the beginning of
                the project.

--sublist file  File here should be the name of a plain text (.txt) file.
                This file should have the names of subjects that you wish to
                download from XNAT; all other subjects in the provided project
                will be ignored.

                If you do not include this argument then data will be
                downloaded for ALL subjects in the specified project.

--exclude file  File here should be the name of a plain text (.txt) file.
                This file should have keywords of the types of scans that you
                want to EXCLUDE from your download.

                Example : if your scan has both resting states (e.g., 'ME
                Resting 1' and 'ME Resting 2') and task runs (e.g., 'ME Task 1'
                and 'ME Task 2') and you only wanted the resting state scans,
                your text file would specify 'ME Task' (without the quotes); in
                this case, only ME Resting 1 and 2 would be downloaded.

--include file  File here should be the name of a plain text (.txt) file.
                Similar to --exclude, this file should have keywords of the
                types of scans that you want to INCLUDE in your download.

                Example : if your scan has both resting states (e.g., 'ME
                Resting 1' and 'ME Resting 2') and task runs (e.g., 'ME Task 1'
                and 'ME Task 2') and you only wanted the resting state scans,
                your text file would specify 'ME Resting' (without the quotes);
                in this case, only ME Resting 1 and 2 would be downloaded.

                Note: while you can use both --exclude and --include when
                running this script, it is probably to your benefit to only use
                one.

-u username     The username that you are accessing XNAT with; you have to make
                sure this user has appropriate access to the project you're
                planning on downloading data from!

                This will default to the user you are signed in to the local
                server as, so you only need specify this if (1) your local
                username is different from your xnat username or (2) you want
                to access XNAT with a different user's credentials.

project         This is the XNAT-style project name that you wish to download
                data from.

===============================================================================
                                    Examples
===============================================================================
$ /opt/xnat/get_data.py MY_PROJECT
    The minimum use case, this will download scans for all the subjects from
    MY_PROJECT experiment, excluding localizer/calibrations scans and DICOMs

$ /opt/xnat/get_data.py -av MY_PROJECT
    Same as above, but this will include the localizer/calibration scans, and
    will print a minimal number of progress updates

$ /opt/xnat/get_data.py -aavv MY_PROJECT
    Same as above but now all the DICOM files will be downloaded, too, and you
    will get slightly more progress updates

$ /opt/xnat/get_data.py -vvv --include my_scans.txt MY_PROJECT
    Where my_scans.txt specifies 'MP-Rage', this will download any anatomical
    scans with 'MP-Rage' in the scan name for every subject from the MY_PROJECT
    experiment. This will print a somewhat significant number of progress
    updates

$ /opt/xnat/get_data.py -aavv --sublist my_subjects.txt MY_PROJECT
    Where my_subjects.txt specifies the subject IDs as they appear on XNAT for
    those subjects whose data I am interested in downloading. This will
    download ALL the data for the specified subjects, and will print a
    reasonable number of progress updates

$ /opt/xnat/get_data.py -vv -s 2016-01-01 -e 2017-01-01 MY_PROJECT
    This will download all subjects from MY_PROJECT scanned during the 2016
    calendar year, and will print a reasonable number of progress updates
