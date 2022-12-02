# XtraBackupAutomation

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Todo](#todo)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Installation](#installation)
- [Sources & Links](#sources--links)
- [License](#license)


## Introduction
The intention of this project is to automate Percona's XtraBackup in a way that is easy to understand and manipulate.
'XtraBackupAutomation' is a simple  program that allows for the scheduling of MySQL backups using systemd and Percona's 
XtraBackup tool. It also allows automatic archiving of these backups.

This is my first open source project, and I am looking forward to contributing back to the community. Constructive
feedback and feature requests are welcome as I hope to maintain a useful piece of software for everyone to use.

Thanks!


## Features
- Scheduled Percona's XtraBackups for MySQL using systemd services and timers
- Automatic backup archival using python's shutil.make_archive
- Robust configuration intended to give users the ability to enable/disable features, change file locations, and 
create the program they need with ease
- Easy to read, well commented, one file implementation

## Todo
- Pull out the commonalitiesso between _create_full_backup && _create_partial_backup to their own method
  - This isn't very complicated as the pepxect portion of these methods have turned out to be almost identical. This will likely come soon
- Add rough 'unzip and restore backup' instructions
  - I think it would be helpful to at the very least give a little sample of unzipping an archived backup

## Requirements

#### Developed On
- **OS:**
  - Debian GNU/Linux 10 (buster)
- **Python Version:**
  - Python 3.10.4
- **Python Packages**
  - **Name:** pexpect, **Version:** 4.8.0
- **Percona XtraBackup Version:**
  - XtraBackup version 8.0.28-21 based on MySQL server 8.0.28 Linux (x86_64)
- **MySQL**
  - MySql  Ver 8.0.28 for Linux on x86_64 (MySQL Community Server - GPL)
  
#### Required Python Libraries
- pexpect 

#### Required Files
- xtrabackupautomator.py
- xtrabackupautomator.service
- xtrabackupautomator.timer

## Configuration
```

== db ==
    -un
        [DEFAULT_VALUE: ""]
        XtraBackup user you set up during your initial configuration of Percona's XtraBackup
    
    -pw
        [DEFAULT_VALUE: ""]
        This user's password

    -host
        [DEFAULT_VALUE: "localhost"]
        The IP of your database 

    -port
        [DEFAULT_VALUE: 3306]
        The port to access database 


== folder_names ==
    -base_dir 
        [DEFAULT_VALUE: "/data/backups/"]
        The root directory for all backup related things. Holds current backup and any archived backups.
        This is the default location and is reflected in the setup as we request you create this folder.
        If you change this directory in the config this change must be reflected in the setup.

    -datadir 
        [DEFAULT_VALUE: "mysql/"]
        Folder that current backups will be saved to. This would be the folder that holds the base backup and any 
          incremental backups before they are archived
        If you change this directory in the config this change must be reflected in the setup.
        *** XtraBackupAutomator WILL ARCHIVE AND DELETE ANYTHING IN HERE. THIS SHOULD BE AN EMPTY FOLDER, NOT UTILIZED BY ANYTHING ELSE.

    -archivedir 
        [DEFAULT_VALUE: "archive/"]
        Folder that a group of backups will be archived to. 
        If you change this directory in the config this change must be reflected in the setup.
        *** XtraBackupAutomator COULD POTENTIALLY DELETE ANY NON-DIRECTORY IN HERE.

== file_names ==
    -basefolder_name
        [DEFAULT_VALUE: "base"]
        Foldername for the base backup

    -incrementalfolder_perfix
        [DEFAULT_VALUE: "inc_"]
        Folder name prefix for incremental backups. 
        Suffixed with the current number of incremental backups minus one
        e.g. 'inc_0'

    -archive_name_prefix
        [DEFAULT_VALUE: "database_backup_"]
        Prefix for the archive files. 
        Suffixed by the datetime of the archive
        e.g. 'database_backup_11_28_2022__06_25_03.tar.gz'


== archive_settings ==
    -allow_archive
        [DEFAULT_VALUE: True]
        An override to enable/disable all archive settings.
        Currently, disabling this will cause the program to do a base backup and then incremental backups forever.

    -archive_zip_format
        [DEFAULT_VALUE: "gztar"]
        The default archive file type. I like tarballs because they zip our large database into a manageable file. 
        However, tarballs can take a long time to create and require a fair amount of resources if your DB is large. 
        This setting will depend on your system and the size of your DB. I recommend playing around with this.
        Other zip options: [Shutil Man Page](https://docs.python.org/3/library/shutil.html#shutil.make_archive)

    -archived_bu_count
        [DEFAULT_VALUE: 7]
        Keep x archived backups, once this threshold is reached the oldest archive will be deleted.
        Archiving daily, this is a week of archives.

    -enforce_max_num_bu_before_archive
        [DEFAULT_VALUE: True]
        One of two ways to 'force archive' of backups. 
        This counts the # of incremental backup folders and initiates the archives once that number is reached. 
        A sample use case is that in your systemd timer file is scheduled to do 5 backups throughout the day, so setting this to 
          true and max_num_bu_before_archive_count set to 4 (because we do not count the base) would give you a 'daily archive'

    -max_num_bu_before_archive_count
        [DEFAULT_VALUE: 4]
        The max number of incremental backups to do before we archive (does not count the base). 
        Set to 0 to archive after each base

    -enforce_archive_at_time
        [DEFAULT_VALUE: False]
        One of two ways to 'force archive' of backups. 
        This will archive what ever base or incremental folders exist if a backup is happening within the 
          archive_at_utc_24_hour hour. This is intended to make it easier to schedule when your archive and base backup occur. 
        These can be resource intensive and so it is nice to do at off hours.
        *If this program is scheduled to run more than once during the 'archive_at_utc_24_hour' hour each run will cause an archive.

    -archive_at_utc_24_hour
        [DEFAULT_VALUE: 6]
        If a backup happens within this hour we will archive w/e was previously there and create a new base.
        Matching this with a time setup in your xtrabackupautomator.timer allows you to choose when your backups will 
          occur.
        No explicit consideration for daylight savings time. 
        Defaults to the hour of 1:00am EST, 6:00am UTC.


== general_settings ==
    -backup_command_timeout_seconds
        [DEFAULT_VALUE: 30]
        Give us 'backup_command_timeout_seconds' seconds for the command to respond. 
        This is not the same as saying 'a backup can only take this long'.

    -max_time_between_backups_seconds
        [DEFAULT_VALUE: 60*60*24]
        Max number of seconds between this backup and the last.
        If the last backup is older than this we will archive and create a new base. 
        This is in an attempt to prevent an incremental backup that might span days or weeks due to this service being 
          turned off or some such.
        Defaults (arbitrarily) to 24 hours

    -additional_bu_command_params
        [DEFAULT_VALUE: ["no-server-version-check"]]
        Any additional parameters that you wish to pass along to your backup commands.
        We loop this list, put a '--' before each element and append it to the end of our backup commands.
        This gets applied to the base and incremental backup commands.
        These are params that I have found useful.


== log_settings ==
    -is_enabled
        [DEFAULT_VALUE: True]
        Enables/Disables all logging type settings. This was useful in testing so I kept it around.

    -log_child_process_to_screen
        [DEFAULT_VALUE: True]
        If this is set to true the child process's output will be dumped to screen but not actually logged anywhere

    -is_log_to_file
        [DEFAULT_VALUE: True]
        If set to True we will try to log to the 'default_log_file' in the 'default_log_path' directory

    -default_log_path
        [DEFAULT_VALUE: "/var/log/"]
        The path that we will try to place our log file ('default_log_file') 

    -default_log_file
        [DEFAULT_VALUE: "xtrabackupautomator.log"]
        The file name we will try to log to

```

## Installation

Below is a general explanation of how to install and start running this program. I would suggest running the program 
manually via command line a couple times, in a preproduction environment, to verify things are working as you expect.

I am assuming that you have downloaded the required files listed at the top of this readme and placed them somewhere you can manipulate.

_**Unrelated to XtraBackupAutomator, if your XtraBackup and MySQL versions do not match this can cause 
tremendously negative side effects with the Percona XtraBackup software. I have considered adding this check 
before allowing a backup to occur but this has not been necessary for me personally.**_

>___Review Your Config Settings___
>>Review the config section of this readme and alter these settings to your liking.<br>
>Any altered folder paths may affect the create folder instructions below. Alter as necessary.
> 
>___Edit your systemd service and timer___
>> I have not explained how to do this here but have included several links that describe how to do this in the 
>> [Sources & Links](#sources--links) section.
> 
>___Install the required dependencies___
>```
>$ python3 -m pip install pexpect
>```
>___Create the directory for our code to live in___
>``` 
>$ sudo mkdir /lib/xtrabackupautomator
>$ sudo chmod 700 /lib/xtrabackupautomator
>```
>
>___Create the directories for our backups to save to___
>```
>$ sudo mkdir -p /data/backups/mysql
>$ sudo mkdir -p /data/backups/archive
>$ sudo mkdir -p /data/backups/archive/archive_restore
>
>$ sudo chmod 760 /data/backups/mysql
>$ sudo chmod 700 /data/backups/archive
>$ sudo chmod 700 /data/backups/archive/archive_restore
>$ sudo chown -R root:root /data/backups/
>```
>
>___Move your downloaded files___
>```
>$ sudo mv xtrabackupautomator.py /lib/xtrabackupautomator/.
>$ sudo mv xtrabackupautomator.service /etc/systemd/system/.
>$ sudo mv xtrabackupautomator.timer /etc/systemd/system/.
>```
>
>___Enable your servie and timer___
>```
>$ sudo systemctl daemon-reload
>
>$ sudo systemctl enable xtrabackupautomator.service
>$ sudo systemctl enable xtrabackupautomator.timer
>
>$ sudo systemctl start xtrabackupautomator.timer
>$ sudo systemctl status xtrabackupautomator.timer
>```

## Sources \& Links

- Official Percona XtraBackup Documentation
    - https://docs.percona.com/percona-xtrabackup/8.0/index.html
- Systemctl Overveiw
  - https://fedoramagazine.org/what-is-an-init-system/ 
  - https://www.digitalocean.com/community/tutorials/how-to-use-systemctl-to-manage-systemd-services-and-units
  - https://medium.com/codex/setup-a-python-script-as-a-service-through-systemctl-systemd-f0cc55a42267
- Systemctl Timers Overview
  - https://linuxconfig.org/how-to-schedule-tasks-with-systemd-timers-in-linux
  - https://opensource.com/article/20/7/systemd-timers
- Systemctl Services Details
  - https://www.freedesktop.org/software/systemd/man/systemd.service.html
- Systemctl Timers Details
  - https://www.freedesktop.org/software/systemd/man/systemd.timer.html
- OnCalendar Expected Formats
  - https://www.freedesktop.org/software/systemd/man/systemd.time.html#
- Archive Zip Options
  - https://docs.python.org/3/library/shutil.html#shutil.make_archive

## License
GNU General Public License v3.0


