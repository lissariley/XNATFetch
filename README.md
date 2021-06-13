# XNATFetch
A set of utilities for fetching MRI data from an XNAT server, and doing some organization and preprocessing of the files.

## Known issues
* -k switch to delete concatenated dicoms is not implemented
* Error in one subject stops entire process
* Aux files in subdirectories fail to download.
* If a subject has multiple exams, only one is downloaded

## Planned upgrades
* Make script automatically skip multiecho concatenation if appropriate nifti files already exist, and skip re-downloading auxiliary files
* Possibly pull data from XNAT in parallel to speed up (concatenation is already partially in parallel)
* Possibly make this code play nicely with SLURM for speed
* Add ability to specify data output directory, so it doesn't always dump to the current working dir
* Create executable wrapper for ease of use that activates venv for you?
* Unify/normalize/improve formatting of log output
* Make bigger formatting divisions in log output between major steps in the process
* Add example usage and explanatory text to help output
