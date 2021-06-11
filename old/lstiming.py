import re
import datetime as dt

with open('lsout.txt', 'r') as f:
    text = f.readlines();

dirLineRegex = re.compile('^(/.*):$')
fileCountLineRegex = re.compile('^total [0-9]+$')
fileLineRegex = re.compile('^([drwx\-]{10}) +([0-9]+) +([^\s]+) +([^\s]+) +([0-9]+) +([0-9]{4})-([0-9]{2})-([0-9]{2}) +([0-9]{2}):([0-9]{2}):([0-9]{2}\.[0-9]+) +(-?[0-9]+) +(.*)$')

text = [line.rstrip() for line in text]

currentDir = ''

sizes = []
times = []
names = []
dirs = []
for line in text:
    fileLineMatch = fileLineRegex.match(line)
    dirLineMatch = dirLineRegex.match(line)
    fileCountLineMatch = fileCountLineRegex.match(line)
    if dirLineMatch:
        currentDir = dirLineMatch.group(1)
    if fileLineMatch:
        permissions = fileLineMatch.group(1)
        nLinks      = int(fileLineMatch.group(2))
        user        = fileLineMatch.group(3)
        group       = fileLineMatch.group(4)
        size        = int(fileLineMatch.group(5))
        year        = int(fileLineMatch.group(6))
        month       = int(fileLineMatch.group(7))
        day         = int(fileLineMatch.group(8))
        hour        = int(fileLineMatch.group(9))
        minute      = int(fileLineMatch.group(10))
        fracSecond  = float(fileLineMatch.group(11))
        second      = int(fracSecond)
        microsecond = int((fracSecond - second) * 1000000)
        TZOffset    = int(fileLineMatch.group(12))//100
        timestamp   = dt.datetime(year, month, day, hour, minute, second, microsecond, tzinfo=dt.timezone(dt.timedelta(hours=TZOffset)))
        name        = fileLineMatch.group(13)
        dirs.append(currentDir)
        names.append(name)
        times.append(timestamp)
        sizes.append(size)
        print(line)
        print('   Size:       ', size)
        print('   Timestamp:  ', timestamp)
        print('   currentDir: ', currentDir)
        print('   Name:       ', name)

times, sizes, names, dirs = zip(*sorted(zip(times, sizes, names, dirs)))

speeds = []
for k in range(len(sizes)-1):
    speeds.append(int(sizes[k]/(times[k+1]-times[k]).total_seconds()))

print('Size:          Speed:         Time:         Dir:')
for k in range(len(sizes)-1):
    print('{size}{speed}{time}     {path}'.format(size=str(sizes[k]).ljust(15), speed=str(speeds[k]).ljust(15), time=times[k], path=dirs[k]))
