This directory contains scripts relevant to multi-echo concatenation. 

The `me_concat.py` script should be called as a cronjob approximately every 
hour. It will trawl through /dicom on the AFNIPC and look for recent exams that
have multi-echo scans that need to be concatenated into NIFTI format. It will 
then call nii_mdir_sdcme in /home/sdcme/bin (written by wl358) as a subprocess
to perform the actual concatenation. Check `me_concat.py` docstring for more
information about how it determines which exams need to be concatenated.

You can also check me_concat.log to see the output of `me_concat.py` for info
about which exams have recently been concatenated. Information in the log file
is limited, but should contain details about when each exam was concatenated,
how many scans were concatenated (each '.' corresponds to a single scan), and
whether any scans within an exam had missing DICOM files (i.e., the scans were
aborted early). It might be good to check this log file every now and again to
ensure that `me_concat.py` is being properly called.

The `utils.py` script is a helper module that provides many of the functions
utilized by `me_concat.py`. HOWEVER, it can also be called as a command-line
script. See the docstring at the top of that script for instructions on usage.
At minimum, you can simply call `python utils.py EXAMNUMBER` where EXAMNUMBER
is the number corresponding to the relevant exam that needs to be concatenated.

NOTE: `utils.py` also exists in /home/sdcme/bin as concat_func. This may seem
redundant, but /home/sdcme/bin is on sdcme's $PATH, so you can call that from
any directory. You can check what arguments can be provided to concat_func by
typing "concat_func --help" from the command line.

`Requirements.txt` notes Python modules that are required for these scripts to be
executed.
