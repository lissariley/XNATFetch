# XNATFetch
A set of utilities for fetching MRI data from an XNAT server, and doing some organization and preprocessing of the files.

## Requirements
* python 3.x (tested on 3.6)
    * [pydicom](https://pypi.org/project/pydicom/)
    * [pyxnat](https://pypi.org/project/pyxnat/)
    * [python-dateutil](https://pypi.org/project/python-dateutil/)
* [afni](https://afni.nimh.nih.gov/)
    * Primarily, the afni script [Dimon](https://afni.nimh.nih.gov/pub/dist/doc/program_help/Dimon.html), for concatenating multi-echo DICOM files.

## Installation
Setup of a [python virtual environment](https://docs.python.org/3/tutorial/venv.html) is the recommended method of preparing the python dependencies, but they can also be installed system-wide.

Download or clone this repository, and place it in a place accessible from the same machine where the data will be downloaded.

## Example usage:
`python /your/path/to/pull_and_process_MRI_data.py`
* Display basic help for `pull_and_process_MRI_data.py`

`python /your/path/to/pull_and_process_MRI_data.py -h`
* Display detailed help for `pull_and_process_MRI_data.py`

`python /your/path/to/pull_and_process_MRI_data.py -u drjanedoe -vv 123456789`
* Pull all subjects and all data for XNAT username "drjanedoe", project # 123456789

`python /your/path/to/pull_and_process_MRI_data.py -u drjanedoe --sub-list "SUB1,SUB2,SUB7" -vv 123456789`
* Pull three specific subjects, and all data for XNAT username "drjanedoe", project # 123456789

`python /your/path/to/pull_and_process_MRI_data.py -u drjanedoe --include_list "DICOM" -vv 123456789`
* Pull all subjects, only files from resources marked "DICOM" for XNAT username "drjanedoe", project # 123456789

## Tips
### Set up a virtual environment
Run this command to create a virtual environment called "xnat" (substitute the path where you want it to exist)
> python -m venv /path/where/you/want/virtualenv/called/xnat
Edit your bash profile to create a convenient alias so it's easy to activate it:
> echo "# Set up convenient alias for activating xnat virtual environment" >> ~/.profile
> echo 'alias xnat=" \' >> ~/.profile
> echo "   source /home/shared/aclab-fmri/Studies/33_MOTIP2018/scripts/xnat/xnatenv/bin/activate; \" >> ~/.profile
> echo "   printf '\nxnat python environment activated, for getting and preprocessing MRI data from XNAT server. \" >> ~/.profile
> echo 'Type deactivate to deactivate environment.\n\n'"'
Then activate your environment by typing
> xnat

## Known issues
* -k switch to delete concatenated dicoms is not implemented
* Aux files in subdirectories fail to download.
* Skipping pre-existing concatenation is not working yet

## Planned upgrades
* Make script automatically skip multiecho concatenation if appropriate nifti files already exist, and skip re-downloading auxiliary files
* Possibly pull data from XNAT in parallel to speed up (concatenation is already partially in parallel)
* Possibly make this code play nicely with SLURM for speed
* Add ability to specify data output directory, so it doesn't always dump to the current working dir
* Create executable wrapper for ease of use that activates venv for you?
* Unify/normalize/improve formatting of log output
* Make bigger formatting divisions in log output between major steps in the process
* Add example usage and explanatory text to help output
