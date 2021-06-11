import argparse

parser = argparse.ArgumentParser(description='Download data from HD-HNI ' +
                                 'XNAT instance.')

# # if this is being run on HD-HNI server, don't require input of username
# if socket.gethostname() != 'hd-hni.cac.cornell.edu': uid_req = True
# else: uid_req = False
uid_req = True;

default_xnat_server = 'fh-mi-cmrifserv.human.cornell.edu'
default_xnat_port = '8080'
default_xnat_path = '/xnat'

parser.add_argument('project',
                    help='Name of XNAT project to download data from.'    )
parser.add_argument('-u',dest='user',metavar='netid',required=uid_req,
                    help='NetID for XNAT access; password will be '       +
                    'requested via command line. Only required if you '   +
                    'are not running this on the HD-HNI server!'          )
parser.add_argument('-x',dest='xnat_address',required=False,
                    help='IP address or hostname of XNAT server. Do not ' +
                    'include port or any other parts of the address here.'+
                    'Default is \'' + default_xnat_server + '\'')
parser.add_argument('-p',dest='xnat_port',required=False,
                    help='Port for communicating with xnat server. '      +
                    'Default is \'' + default_xnat_port + '\'')
parser.add_argument('-t',dest='xnat_path',required=False,
                    help='URL path for xnat server. Default is \''        +
                    default_xnat_path + '\'')
parser.add_argument('-a',dest='all_data',action='count',default=0,
                    help='Pull data for every scan, including '           +
                    'calibrations and localizers. Increase number of '    +
                    'a\'s (e.g., -aa) to pull more data. NOTE: this '     +
                    'will dramatically slow down program.'                )
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
parser.add_argument('--sublist',dest='sublist',metavar='file',default=None,
                    help='Text file specifying subjects to get data for.' +
                    ' Default: pull all subjects'                         )
parser.add_argument('--include',dest='include',metavar='file',default=None,
                    help='Text file specifying series description for '   +
                    'data to download. Default: download all data.'       )
parser.add_argument('--exclude',dest='exclude',metavar='file',default=None,
                    help='Text file specifying series descriptions for '  +
                    'data NOT to download. Default: exclude '             +
                    'calibration/localizer'                               )
parser.add_argument('--BIDS',action='store_true',default=False,
                    help='Organize data into BIDS format immediately '    +
                    'after download. THIS FEATURE IS IN BETA -- use at '  +
                    'your own risk! Default: off'                         )
params = vars(parser.parse_args())

# if we're on HD-HNI server, get the user ID
if not params['user']: params['user'] = os.environ['USER']
