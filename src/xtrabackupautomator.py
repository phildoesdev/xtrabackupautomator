#!/usr/bin/python3
"""
    XtraBackupAutomation automates Percona's XtraBackup
    Copyright (C) 2022 PhilDoes

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

    Contact PhilDoes at XtraBackupAutomation@phildoes.dev
"""

from enum import Enum, IntEnum
from os import path, remove, listdir
import sys
from datetime import datetime, timezone
import pexpect
import json
import time
import shutil


class LogLvl(IntEnum):
    """
    Summary/Notes:
        IntEnum for the severity of the log msg. Dumping up here in an attempt to keep this program one file.
    Version:
        1.0.0
    Updated:
        12/01/22 phil
    """
    TRACE = 1
    DEBUG = 2
    INFO = 3
    WARN = 4
    ERROR = 5
    FATAL = 6
    JCTL_ONLY = 7   # Will never log to log file- print only


class XtraBackupAutomator:
    """
    Summary/Notes:
        Automate Percona's XtraBackup utility
    Version:
        1.0.0
    Created:
        12/01/2022 PhilDoes
    """

    def __init__(self):

        # Pulled all configs into the main file to keep this program simple and one file
        self._config_structs = {
            "db": {
                "un": "YOURUSER",
                "pw": "YOURPASS",
                "host": "localhost",
                "port": "3306"
            },
            "folder_names": {
                "base_dir": "/data/backups/",
                "datadir": "mysql/",            # *** XtraBackupAutomator WILL ARCHIVE AND DELETE ANYTHING IN HERE. THIS SHOULD BE AN EMPTY FOLDER, NOT UTILIZED BY ANYTHING ELSE.
                "archivedir": "archive/",       # *** XtraBackupAutomator COULD POTENTIALLY DELETE ANY NON-DIRECTORY IN HERE.
            },
            "file_names": {
                "basefolder_name": "base",
                "incrementalfolder_perfix": "inc_",
                "archive_name_prefix": "database_backup_",
            },
            "general_settings": {
                "backup_command_timeout_seconds": 30,
                "max_time_between_backups_seconds": 60*60*20,
                "additional_bu_command_params": ["no-server-version-check"]
            },
            "archive_settings": {
                "allow_archive": True,                          # An override to enable/disable all archive settings
                "archive_zip_format": "gztar",
                "archived_bu_count": 7,                         # number of archives to store before they get deleted
                "enforce_max_num_bu_before_archive": False,     # one of two ways to control when we archive
                "max_num_bu_before_archive_count": 4,
                "enforce_archive_at_time": True,                # one of two ways to control when we archive
                "archive_at_utc_24_hour": 6,                    # Matching this with a time setup in your xtrabackupautomator.timer allows
                                                                #   you to choose when your backups will occur. This is useful for large DBs
            },
            "log_settings": {
                "is_enabled": True,                             # An override to enable/disable all logging
                "log_child_process_to_screen": True,
                "is_log_to_file": True,
                "default_log_path": "/var/log/",
                "default_log_file": "xtrabackupautomator.log",
            }
        }

    """ * * * * """
    """ GETTERS """
    """ * * * * """
    def _get_config_db(self):
        """
        Return the config sturct loaded from file for our database connection
        :return: dict
        """
        return self._config_structs["db"]

    def _get_config_folder_names(self):
        """
        Return the 'folder_names' dict from the config
        :return: dict
        """
        return self._config_structs["folder_names"]

    def _get_config_file_names(self):
        """
        Return the 'file_names' dict from the config
        :return: dict
        """
        return self._config_structs["file_names"]

    def _get_config_archive_settings(self):
        """
        Return the 'archive_settings' dict from the config
        :return: dict
        """
        return self._config_structs["archive_settings"]

    def _get_config_general_settings(self):
        """
        Return the 'general_settings' dict from the config
        :return: dict
        """
        return self._config_structs["general_settings"]

    def _get_config_logging(self):
        """
        Return the config sturct loaded from file for our logging settingss
        :return: dict
        """
        return self._config_structs["log_settings"]

    def _get_config_folder_base_dir(self):
        """
        The root directory for all backup related things. Holds current backup and any archived backups.
        This is the default location and is reflected in the setup as we request you create this folder.
        :return: str
        """
        return self._get_config_folder_names()["base_dir"]

    def get_config_folder_datadir_path(self):
        """
        Folder that current backups will be saved to. This would be the folder that holds the base backup and any
          incremental backups before they are archived
        *** XtraBackupAutomator WILL ARCHIVE AND DELETE ANYTHING IN HERE. THIS SHOULD BE AN EMPTY FOLDER, NOT UTILIZED BY ANYTHING ELSE.
        :return: str
        """
        return self._get_config_folder_base_dir() + self._get_config_folder_names()["datadir"]

    def _get_config_folder_archivedir_path(self):
        """
        Folder that a group of backups will be archived to.
        *** XtraBackupAutomator COULD POTENTIALLY DELETE ANY NON-DIRECTORY IN HERE.
        :return: str
        """
        return self._get_config_folder_base_dir() + self._get_config_folder_names()["archivedir"]

    def _get_config_file_basefolder_name(self):
        """
        Foldername for the base backup
        :return: str
        """
        return self._get_config_file_names()["basefolder_name"]

    def _get_config_file_basefolder_name_path(self):
        """
        Full path for the base backup
        :return: str
        """
        return self.get_config_folder_datadir_path() + self._get_config_file_basefolder_name()

    def _get_config_file_archive_name_prefix(self):
        """
        Prefix for the archive files.
        Suffixed by the datetime of the archive
        e.g. 'database_backup_11_28_2022__06_25_03.tar.gz'
        :return: str
        """
        return str(self._get_config_file_names()["archive_name_prefix"])

    def _get_config_file_incrementalfolder_perfix(self):
        """
        Get the incrementalfolder_perfix field from the general config.
        Folder name prefix for incremental backups.
        Suffixed with the current number of incremental backups minus one
        e.g. 'inc_0'
        :return: str
        """
        return self._get_config_file_names()["incrementalfolder_perfix"]

    def _get_config_archive_enforce_max_num_bu_before_archive(self):
        """
        One of two ways to 'force archive' of backups.
        This counts the # of incremental backup folders and initiates the archives once that number is reached.
        A sample use case is that in your systemd timer file is scheduled to do 5 backups throughout the day, so setting this to
          true and max_num_bu_before_archive_count set to 4 (because we do not count the base) would give you a 'daily archive'
        :return: int
        """
        return bool(self._get_config_archive_settings()["enforce_max_num_bu_before_archive"])

    def _get_config_archive_max_num_bu_before_archive_count(self):
        """
        Get max_num_bu_before_archive_count field from the general config.
        The max number of incremental backups's to do before we archive (does not count the base).
        Set to 0 to archive after each base
        :return: int
        """
        return int(self._get_config_archive_settings()["max_num_bu_before_archive_count"])

    def _get_config_general_enforce_archive_at_time(self):
        """
        One of two ways to 'force archive' of backups.
        This will archive what ever base or incremental folders exist if a backup is happening within the
          archive_at_utc_24_hour hour. This is intended to make it easier to schedule when your archive and base backup occur.
        These can be resource intensive and so it is nice to do at off hours.
        *If this program is scheduled to run more than once during the 'archive_at_utc_24_hour' hour each run will cause an archive.

        :return: bool
        """
        return bool(self._get_config_archive_settings()["enforce_archive_at_time"])

    def _get_config_archive_archive_at_utc_24_hour(self):
        """
        If a backup happens within this hour we will archive w/e was previously there and create a new base.
        Matching this with a time setup in your xtrabackupautomator.timer allows you to choose when your backups will
          occur.
        No explicit consideration for daylight savings time.
        :return: int
        """
        return int(self._get_config_archive_settings()["archive_at_utc_24_hour"])

    def _get_config_archive_archived_bu_count(self):
        """
        If a backup happens within this hour we will archive w/e was previously there and create a new base.
        Matching this with a time setup in your xtrabackupautomator.timer allows you to choose when your backups will
          occur.
        No explicit consideration for daylight savings time.
        :return: int
        """
        return int(self._get_config_archive_settings()["archived_bu_count"])

    def _get_config_archive_archive_zip_format(self):
        """
         The default archive file type. I like tarballs because they zip our large database into a manageable file.
        However, tarballs can take a long time to create and require a fair amount of resources if your DB is large.
        This setting will depend on your system and the size of your DB. I recommend playing around with this.
        Other zip options: [Shutil Man Page](https://docs.python.org/3/library/shutil.html#shutil.make_archive)
        :return: str
        """
        return str(self._get_config_archive_settings()["archive_zip_format"])

    def _get_config_general_backup_command_timeout_seconds(self):
        """
        Give us 'backup_command_timeout' seconds for the command to respond.
        This is not the same as saying 'a backup can only take this long'.
        :return: int
        """
        return int(self._get_config_general_settings()["backup_command_timeout_seconds"])

    def _get_config_general_max_time_between_backups_seconds(self):
        """
        Max number of seconds between this backup and the last.
        If the last backup is older than this we will archive and create a new base.
        This is in an attempt to prevent an incremental backup that might span days or weeks due to this service being
          turned off or some such.
        Defaults (arbitrarily) to 24 hours
        :return: int
        """
        return int(self._get_config_general_settings()["max_time_between_backups_seconds"])

    def _get_config_general_additional_bu_command_params(self):
        """
        Any additional parameters that you wish to pass along to your backup commands.
        We loop this list, put a '--' before each element and append it to the end of our backup commands.
        This gets applied to the base and incremental backup commands.
        These are params that I have found useful.
        :return: list
        """
        return self._get_config_general_settings()["additional_bu_command_params"]

    def _get_config_db_un(self):
        """
        Get the username for the extrabu sql user to allow us to take the backup
        :return:
        """
        return self._get_config_db()["un"]

    def _get_config_db_pw(self):
        """
        Get the username for the extrabu sql user to allow us to take the backup
        :return:
        """
        return self._get_config_db()["pw"]

    def _get_config_db_host(self):
        """
        Get the username for the extrabu sql user to allow us to take the backup
        :return:
        """
        return self._get_config_db()["host"]

    def _get_config_db_port(self):
        """
        Get the username for the extrabu sql user to allow us to take the backup
        :return:
        """
        return self._get_config_db()["port"]

    def _get_config_logging_file_path_full(self):
        """
        Returns the full path to the log file (if there is one)
        :return: string
        """
        return str(self._get_config_logging()["default_log_path"]) + str(self._get_config_logging()["default_log_file"])

    def _get_config_logging_is_log_to_file(self):
        """
        If set to True we will try to log to the 'default_log_file' in the 'default_log_path' directory
        :return: bool
        """
        return bool(self._get_config_logging()["is_log_to_file"])

    def _get_config_logging_is_enabled(self):
        """
        Enables/Disables all logging type settings. This was useful in testing, so I kept it around.
        :return: bool
        """
        return bool(self._get_config_logging()["is_enabled"])

    def _get_config_logging_log_child_process_to_screen(self):
        """
        If this is set to true the child process's output will be dumped to screen but not actually logged anywhere
        :return: bool
        """
        return bool(self._get_config_logging()["log_child_process_to_screen"])

    """* * * * * *"""
    """  Methods  """
    """* * * * * *"""
    def log(self, msg='', e=None, lvl=LogLvl.TRACE, is_print=True):
        """
        public interface for the log method...
        :param msg: string
            message to log
        :param e: string
            exception
        :param lvl:  LogLvl(IntEnum)
            the 'level' of this log... allows us to sort errors out quickly
        :param is_print: bool
             Do we want to print(...) to screen... default True
        """
        try:
            self._log(msg=msg, e=e, lvl=lvl, is_print=is_print)
        except Exception as ex:
            print("Logger Failed || HFBVLDWU || {exception}".format(exception=repr(ex)))

    def _log(self, msg='', e=None, lvl=LogLvl.TRACE, is_print=True):
        """
        Logs to journalctl + file if the setting is set.
        This was initially its own class so some things might look a little weird b/c of that. I thought having one file
            was worth it so I rolled this and our config into the main program.
        :param msg: string
            message to log
        :param e: string
            exception
        :param lvl:  LogLvl(IntEnum)
            the 'level' of this log... allows us to sort errors out quickly
        :param is_print: bool
             Do we want to print(...) to screen... default True
        """
        if not self._get_config_logging_is_enabled():
            return
        # It is convenient to build out a string that we can pass around
        print_msg_str = ""
        try:
            # try to avoid invalid loglevels
            if not isinstance(lvl, LogLvl):
                lvl = LogLvl.TRACE

            curr_datetime = time.ctime()
            # turn our exception message into a str and the ncelan it up
            e = repr(e)
            msg = msg.replace('\n', '').replace('\r', '').replace('\t', '')

            # Begin building out our log msg
            print_msg_str += lvl.name.ljust(8, ":")
            print_msg_str += " " + curr_datetime + " | "
            if msg.strip() != '':
                print_msg_str += "Message: \"" + msg + "\", "
            if e.strip() != "''":
                print_msg_str += "e: " + e

            if is_print:
                print(print_msg_str, flush=True)

            # we're going to be more choosy about what gets written to file
            if self._get_config_logging_is_log_to_file() and lvl != LogLvl.JCTL_ONLY:
                log_file_path = self._get_config_logging_file_path_full()
                # Sanity Check
                if print_msg_str is None or print_msg_str.strip() == '':
                    raise Exception("You are attempting to log an empty message")
                # Sanity check
                if log_file_path == '':
                    raise Exception("Path should not be empty")
                # if the file doesn't exist try to create it so that we can append to it
                if not path.exists(log_file_path):
                    with open(log_file_path, "w"):
                        pass
                # Append to file
                with open(log_file_path, "a") as fw:
                    fw.write(print_msg_str)
                    fw.write("\n")

        except Exception as ex:
            print("Error In Logger 0IT6OO3C. [{exception}]".format(exception=ex))

    def _create_full_backup(self):
        """
        Execute the XtraBackup command to create a full backup to act as the 'base' backup.
        """
        self._log(msg="Begin Executing 'Create Full Backup'", lvl=LogLvl.TRACE)
        command_timeout = self._get_config_general_backup_command_timeout_seconds()             # Give us X minutes to compelte the update before failing to timeout
        cmd_un = self._get_config_db_un()                                               # This is the un for the db user that XtraBackup wants to use
        cmd_pw = self._get_config_db_pw()                                               # This is the response we send to the initial command to enter the PW for this user.
        cmd_host = self._get_config_db_host()
        cmd_port = self._get_config_db_port()
        cmd_target_dir = self._get_config_file_basefolder_name_path()                   # Path to our base folder update
        pexpect_process = None                                                          # Set to none here so that we can do our try/catch/final correctly

        # Construct the base for our xtrabackup command
        full_backup_cmd_txt = "sudo xtrabackup --user="+str(cmd_un)+" --password --host="+str(cmd_host)+" --port="+str(cmd_port)+" --backup --target-dir="+str(cmd_target_dir)

        # If there are additional command params that we wish to build out (according to config) we should do that here
        for _cmd_param in self._get_config_general_additional_bu_command_params():
            # Sanity check
            if str(_cmd_param).strip() == '':
                continue
            # Add this param with a space before and after for safety
            full_backup_cmd_txt += ' --' + str(_cmd_param).strip() + ' '

        try:
            # Use pexpect to send the bu command and wait for password prompt.
            pexpect_process = pexpect.spawn(full_backup_cmd_txt, timeout=command_timeout, echo=False, encoding='utf-8')
            self._log(msg="Child process created. ProcessID: [{pid}], FileDescriptor: [{fd}]".format(pid=pexpect_process.pid, fd=pexpect_process.child_fd), lvl=LogLvl.INFO)

            # Returns index of response found, so we are hoping for found_response == 0
            found_response = pexpect_process.expect(['Enter password', pexpect.TIMEOUT], timeout=command_timeout)

            # Waiting for PW prompt. If we find it correctly, send the password.
            if found_response == 0:
                pexpect_process.sendline(cmd_pw)
            elif found_response == 1:
                pexpect_process.close()
                raise Exception("Pexpect timed out waiting for password prompt. G4L3JRBL")

            # If requested, push child processes output to screen, otherwise hide it b/c it can be quite annoying.
            if self._get_config_logging_is_enabled() and self._get_config_logging_log_child_process_to_screen():
                pexpect_process.logfile = sys.stdout

            self._log(msg="Waiting for child process to finish executing...", lvl=LogLvl.INFO)

            # xtrabackup doesn't exit() the way pexpect expects which causes pexpect to hang forever on .wait(). Reading until EOF compensates for this
            # Python's subprocess module doesn't have this problem, but I think pexpect is a nicer tool
            while True:
                try:
                    pexpect_process.read_nonblocking()
                except pexpect.EOF:
                    break
                except Exception as ex:
                    self._log(msg="Unexpected exception waiting for child process to finish.", e=ex, lvl=LogLvl.INFO)
                    pexpect_process.close()  # This is a redundant close() call, but I like it here for readability
                    raise

            # If after reading all these lines our child process is still alive we can seemingly count on wait() to close properly. We dont hit here and I'm not sure if we actually need this but it seems safe.
            if pexpect_process.isalive():
                pexpect_process.wait()
            # Close so that we can get our response codes and what have you
            pexpect_process.close()

            # We expect an exit status of 0 from the xtrabackup command on a successful bu
            if pexpect_process.exitstatus != 0:
                self._log(msg="Failed to create 'Full Backup'. Non-zero return code. SDDBDCIM", lvl=LogLvl.ERROR)
                raise Exception("Failed to create 'Full Backup'. Non-zero return code. SDDBDCIM")
        except Exception as ex:
            self._log(msg="Failed to execute command 'Full Backup' 4YYQ6AEV", e=ex, lvl=LogLvl.ERROR)
            # we failed, so lets try to delete this folder. No use in having afolder we can't incremnet off of or restore from
            self._remove_directory(cmd_target_dir)
            raise Exception("Failed to execute command 'Full Backup' 4YYQ6AEV ", ex)
        finally:
            # Just incase... Always try to make sure we're cleaning up after ourselves
            if pexpect_process is not None:
                self._log(msg="Closing spawned child process. ProcessID: [{pid}].".format(pid=pexpect_process.pid), lvl=LogLvl.INFO)
                pexpect_process.close()
            self._log(msg="Finished Executing 'Create Full Backup'", lvl=LogLvl.TRACE)

    def _create_partial_backup(self, target_dir_suffix):
        """
        Execute the XtraBackup command to create an incremental backup

        :param target_dir_suffix: int
            The suffix for the incremental backup folder. 0 to w/e the max is set to in the config
            -1 if we didnt find a previously declared inc_ folder (only the base exists)
        """
        self._log(msg="Begin Executing 'Create Partial Backup'", lvl=LogLvl.TRACE)
        command_timeout = self._get_config_general_backup_command_timeout_seconds()
        cmd_un = self._get_config_db_un()           # This is the un for the db user that XtraBackup wants to use
        cmd_pw = self._get_config_db_pw()           # This is the response we send to the initial command to enter the PW for this user.
        cmd_host = self._get_config_db_host()
        cmd_port = self._get_config_db_port()
        target_dir_suffix = int(target_dir_suffix)  # just make sure this is an int
        cmd_incremental_basedir = ""                # This is the directory of the last backup that we are incrementing from. Read percona documentation for more information. Declaring here for readability
        pexpect_process = None                      # Set to none so that we can do our try/catch/final correctly
        cmd_target_dir = self.get_config_folder_datadir_path() + self._get_config_file_incrementalfolder_perfix() + str(target_dir_suffix)  # This is the directory of this incremental backup

        """ 
            Determine the incremental-basedir from the target_dir_suffix.
            We know the suffix for this dir is a number x in range [0,n] where n is an integer >= 0. This means we 
                know that our incremental-basedir is always in the folder x-1, or if x<0, our incremental-basedir 
                is the actual base folder
        """
        if target_dir_suffix <= 0:
            # This is the case that our incremental-basedir is the 'base dir'
            cmd_incremental_basedir = self._get_config_file_basefolder_name_path()
        else:
            # This is the case that the incremental-basedir is the inc folder created before this one- (so we have to take this target_dir_suffix -1 for the basedir)
            cmd_incremental_basedir = self.get_config_folder_datadir_path() + self._get_config_file_incrementalfolder_perfix() + str(target_dir_suffix-1)

        # Construct the base for our inc. backup command
        incremental_backup_cmd_txt = "sudo xtrabackup --user="+str(cmd_un)+" --password --host="+str(cmd_host)+" --port="+str(cmd_port)+" --backup --target-dir="+str(cmd_target_dir)+" --incremental-basedir="+str(cmd_incremental_basedir)

        # If there are additional command params that we wish to build out (according to config) we should do that here
        for _cmd_param in self._get_config_general_additional_bu_command_params():
            # Sanity check
            if _cmd_param.strip() == '':
                continue
            # Add this param with a space before and after for safety
            incremental_backup_cmd_txt += ' --' + _cmd_param.strip() + ' '

        try:
            # Use pexpect to send the bu command and wait for password prompt.
            pexpect_process = pexpect.spawn(incremental_backup_cmd_txt, timeout=command_timeout, echo=False, encoding='utf-8')
            self._log(msg="Child process created. ProcessID: [{pid}], FileDescriptor: [{fd}]".format(pid=pexpect_process.pid, fd=pexpect_process.child_fd), lvl=LogLvl.INFO)

            # Returns index of response found, so we are hoping for found_response == 0
            found_response = pexpect_process.expect(['Enter password', pexpect.TIMEOUT], timeout=5)

            # Waiting for PW prompt. If we find it correctly, send the password.
            if found_response == 0:
                pexpect_process.sendline(cmd_pw)
            elif found_response == 1:
                pexpect_process.close()     # Don't need to close here b/c the catch closes for us, but i think it is more readable to close here as well
                raise Exception("Pexpect timed out waiting for password prompt. G4L3JRBL")

            # If requested, push child processes output to screen, otherwise hide it b/c it can be quite annoying.
            if self._get_config_logging_log_child_process_to_screen():
                pexpect_process.logfile = sys.stdout

            self._log(msg="Waiting for child process to finish executing...", lvl=LogLvl.INFO)
            # xtrabackup doesn't exit() the way pexpect expects which causes pexpect to hang forever on .wait(). Reading until EOF compensates for this
            while True:
                try:
                    pexpect_process.read_nonblocking()
                except pexpect.EOF:
                    break
                except Exception as ex:
                    self._log(msg="Unexpected exception waiting for child process to finish.", e=ex, lvl=LogLvl.INFO)
                    pexpect_process.close()  # This is a redundant close() call, but I like it here for readability
                    raise

            # If after reading all these lines our child process is still alive we can seemingly count on wait() to close properly. We dont hit here and I'm not sure if we actually need this but it seems safe.
            if pexpect_process.isalive():
                pexpect_process.wait()

            # Close so that we can get our response codes and what have you
            pexpect_process.close()
            # We expect an exit status of 0 from the xtrabackup command on a successful bu
            if pexpect_process.exitstatus != 0:
                self._log(msg="Failed to create 'Incremental Backup'. Non-zero return code. XMKJIP69", lvl=LogLvl.ERROR)
                raise Exception("Failed to create 'Incremental Backup'. Non-zero return code. XMKJIP69")
        except Exception as ex:
            self._log(msg="Failed to execute command 'Incremental Backup' OPQLD9GC", e=ex, lvl=LogLvl.ERROR)
            # we failed, so lets try to delete this folder. No use in having afolder we can't incremnet off of or restore from
            self._remove_directory(cmd_target_dir)
            raise Exception("Failed to execute command 'Incremental Backup' OPQLD9GC", ex)
        finally:
            # Just incase... Always try to make sure we're cleaning up after ourselves
            if pexpect_process is not None:
                self._log(msg="Closing spawned child process ProcessID: [{pid}].".format(pid=pexpect_process.pid), lvl=LogLvl.INFO)
                pexpect_process.close()
            self._log(msg="Finished Executing 'Create Incremental Backup'", lvl=LogLvl.TRACE)

    def _wipe_bu_folder(self):
        """
        Remove all directories and files from the backupfolder data dir
        ... Loops items in the designated directory and deletes it
        Gets called after we create the archive
        """
        self._log(msg="Begin clean datadir of folders and files.", lvl=LogLvl.TRACE)
        try:
            if path.isdir(self.get_config_folder_datadir_path()):
                for filename in listdir(self.get_config_folder_datadir_path()):
                    tmp_full_path = self.get_config_folder_datadir_path() + filename
                    if path.isdir(tmp_full_path):
                        # Remove dir and its contents
                        shutil.rmtree(tmp_full_path)
                    else:
                        # Remove a file
                        remove(tmp_full_path)
            else:
                raise NotADirectoryError("Unable to find datadir directory to clean. IBPB5DE2")
        except Exception as ex:
            self._log(msg='Failure to clean datadir folders. PHSFJKW9', e=ex, lvl=LogLvl.ERROR)
            raise Exception('Failure to clean datadir folders. PHSFJKW9', ex)
        self._log(msg="Finished clean datadir of folders and files.", lvl=LogLvl.TRACE)

    def _remove_directory(self, dir_path):
        """
        Given a path to a directory attempt to wipe it. We will not remove files in this method. Idk why, just dont
            need that functionaliy so why make something dangerous more powerful than it needs to be?
        * Limited to our data dir (cannot delete outside of it)

        :param dir_path: str
            path to a directory you want to kill
        """
        self._log(msg="Begin remove_dir [{path}]".format(path=dir_path), lvl=LogLvl.TRACE)

        if not path.isdir(dir_path):
            self._log(msg="Attempted to delete a folder that does not exist. Continuing on. HRE0GN1H", lvl=LogLvl.WARN)
            return

        # Verify that this path is in our datadir. If this ever hits persumably something stupid or evil is happening
        if path.commonprefix([self.get_config_folder_datadir_path(), dir_path]) != self.get_config_folder_datadir_path():
            self._log(msg="You tried to delete a folder outside of our datadir. What, are you some kind of mad man?! MVOSVP0F", lvl=LogLvl.FATAL)
            raise Exception("MVOSVP0F")

        try:
            if path.isdir(dir_path):
                shutil.rmtree(dir_path)
            else:
                raise NotADirectoryError("Unable to find the directory to clean. ZSJCEL86")
        except Exception as ex:
            self._log(msg='Failure to clean requested directory. 059XWORQ', e=ex, lvl=LogLvl.ERROR)
            raise Exception('Failure to clean requested directory. 059XWORQ', ex)
        finally:
            self._log(msg="Finished remove_dir [{path}]".format(path=dir_path), lvl=LogLvl.TRACE)

    def _archive_backups(self):
        """
        Go through the datadir and zip everything inside of it and then move to the desired archive folder
        https://docs.python.org/3/library/shutil.html#shutil.make_archive

        Default zip type is a gztar... This can take a long time to zip & unzip as well as use a lot of resources to do so.
        The archive_zip_format can be set at the top of this file in the config_general settings, choose something that makes
               sense for your system and situation.
        """
        self._log("Begin Archiving Backup Files.", lvl=LogLvl.TRACE)

        # Variables that will help output timing info. Declaring here for readability
        begin_time = time.time()
        finished_time = 0

        archive_name = self._get_config_file_archive_name_prefix() + str(time.strftime("%m_%d_%Y__%H_%M_%S", time.gmtime()))
        archive_path = path.join(self._get_config_folder_archivedir_path(), archive_name)

        arhive_result = shutil.make_archive(base_name=archive_path,                                 # Where we are saving to
                                            format=self._get_config_archive_archive_zip_format(),   # How we want to zip this bu? gztar is the default
                                            root_dir=self._get_config_folder_base_dir(),            # reference dir
                                            base_dir=self.get_config_folder_datadir_path())         # directory we want to archive starting at
        finished_time = time.time()
        self._log("Created Archive: [{full_path}] in [{exec_time}] seconds.".format(full_path=arhive_result, exec_time=(finished_time-begin_time)), lvl=LogLvl.DEBUG)
        self._log("Finsihed Archiving Backup Files.", lvl=LogLvl.TRACE)

    def _clean_archive_folder(self):
        """
        We want to keep a certain number of archived backups (defined in the config). Maintain that number.
        Looks in that folder, counts zipped files that start with our naming convention and then deletes the oldest

        *This only ever deletes one archive file, 'the oldest'.. so if config_general_archived_bu_count changes to a lower
            number it is your responsibility to delete the difference
        """
        self._log(msg="Begin cleaning archive folder", lvl=LogLvl.TRACE)
        num_bus_to_keep = self._get_config_archive_archived_bu_count()
        archives_in_dir = 0
        oldest_archive_epoch = 0
        oldest_archive_full_path = ""

        try:
            if path.isdir(self._get_config_folder_archivedir_path()):
                # This is an 'information gathering loop'. We are just seeing what is there and setting flags and such
                for filename in listdir(self._get_config_folder_archivedir_path()):
                    tmp_full_path = self._get_config_folder_archivedir_path() + filename
                    # We are only interested in tar.gz files, no directories
                    if path.isdir(tmp_full_path):
                        continue
                    # this is presumably an archive file, increment 'history seen' count and record its create time
                    if self._get_config_file_archive_name_prefix() in filename:
                        archives_in_dir += 1
                        tmp_this_createtime_epoch = path.getctime(tmp_full_path)
                        # if it's the first or oldest we've found, record that
                        if oldest_archive_epoch == 0 or tmp_this_createtime_epoch < oldest_archive_epoch:
                            oldest_archive_epoch = tmp_this_createtime_epoch
                            oldest_archive_full_path = tmp_full_path
            else:
                raise NotADirectoryError("Unable to find datadir directory to clean. P5DMT5D7")
        except Exception as ex:
            self._log(msg="Error cleaning archive folder. 6UXQVSFF", e=ex, lvl=LogLvl.ERROR)
            raise

        # Some criteria can just return us here and now without the need to do any more work
        attempt_purge_flag = True
        if archives_in_dir <= num_bus_to_keep and attempt_purge_flag:
            self._log(msg="Archive count has not reached the maximum number. No old archives to purge. OD9DDDM2", lvl=LogLvl.TRACE)
            attempt_purge_flag = False
        if (oldest_archive_full_path.strip() == "" or oldest_archive_epoch == 0) and attempt_purge_flag:
            self._log(msg="No archives found. No old archives to purge. 7OZ9QD6M", lvl=LogLvl.TRACE)
            attempt_purge_flag = False
        if not path.exists(oldest_archive_full_path) and attempt_purge_flag:
            self._log(msg="We were asked to purge an archive we could not find. PVFNJTM5", lvl=LogLvl.TRACE)
            attempt_purge_flag = False

        # Now we need to read those flags and determine if we need to purge a archive file or not (only tries to delete 1 at a time)
        try:
            # Sanity checks and then work
            if attempt_purge_flag:
                # Re-check things right before we try to delete. This is kind of sutpid but here I am. I like checking up top for nice error messages and checking again here for my sanity
                if archives_in_dir > num_bus_to_keep and path.exists(oldest_archive_full_path) and self._get_config_file_archive_name_prefix() in oldest_archive_full_path:
                    self._log(msg="*We ahve reached our archived backup limit of {curr_num_archives}/{max_num_archives}. Purging old archive file {archive_name}".format(archive_name=oldest_archive_full_path, curr_num_archives=archives_in_dir, max_num_archives=num_bus_to_keep), lvl=LogLvl.TRACE)
                    remove(oldest_archive_full_path)
                else:
                    raise NameError("Could not find file we were asked to delete: [{archive_path}]. YHR6OF9U".format(archive_path=oldest_archive_full_path))
        except Exception as ex:
            self._log(msg="Failed to clean archive folder. 7XX0M1BE", e=ex, lvl=LogLvl.ERROR)
            raise
        finally:
            self._log(msg="Finished cleaning archive folder", lvl=LogLvl.TRACE)

    def main(self):
        """
        Entry Point for our program.
        """
        # Flags and variables that help us determine where we are
        force_archive_flag = False
        found_base_folder = False
        # We need to determine what 'inc_' suffix we need so we need to look for the last (largest) suffix that exists
        largest_inc_file_found = -1
        # We want to record the datetime of the most recent backup. If it's more than max_time_between_backups_seconds we should archive and do a full backup
        newest_file_found = 0

        # Determine what we need to do. Are we creating a full backup, an incremental backup, or archiving and then creating a full bu?
        # Start by looking for the largest 'inc_' folder in existence, as well as for a 'base' folder. This will tell us what to do next
        for filename in listdir(self.get_config_folder_datadir_path()):
            tmp_full_path = self.get_config_folder_datadir_path() + filename
            tmp_split_filename = filename.split("_")
            if filename.lower() == self._get_config_file_basefolder_name():
                found_base_folder = True
            elif self._get_config_file_incrementalfolder_perfix() in filename and len(tmp_split_filename) == 2:
                # the end of 'inc_'. some number >=0
                tmp_num = int(tmp_split_filename[1])
                if tmp_num > largest_inc_file_found:
                    largest_inc_file_found = tmp_num
            tmp_ctime = path.getctime(tmp_full_path)
            if newest_file_found == 0 or tmp_ctime > newest_file_found:
                newest_file_found = tmp_ctime

        # Get the current utc hour (military time) so we can see if we need to force archive
        utc_hour_now = datetime.now(timezone.utc).hour
        utc_hour_req_force = self._get_config_archive_archive_at_utc_24_hour()

        # There are a couple situations to force an archive... Let's check those here
        if found_base_folder:
            # If we were asked for an archive at a certain hour and a basefolder already exists we will archive
            if self._get_config_general_enforce_archive_at_time() and utc_hour_req_force >= 0 and utc_hour_now == utc_hour_req_force:
                self._log(msg="It is UTC hour [{hour_utc_now}] and 'Force Archive' was requested at hour [{utc_hour_req_force}] so we are going to do that.".format(hour_utc_now=utc_hour_now, utc_hour_req_force=utc_hour_req_force), lvl=LogLvl.DEBUG)
                force_archive_flag = True
            # See if the last update was more than '_get_config_general_max_time_between_backups_seconds' seconds ago. If this is the case we want to archive and create new base. If no base folder was found who cares, gotta create a new base anyways
            if int(time.time() - newest_file_found) > self._get_config_general_max_time_between_backups_seconds():
                self._log(msg="The most recent backup is more than {timebetween} minutes ago. We are archiving and creating a new base backup.".format(timebetween=self._get_config_general_max_time_between_backups_seconds()/60), lvl=LogLvl.DEBUG)
                force_archive_flag = True
            if self._get_config_archive_enforce_max_num_bu_before_archive() and largest_inc_file_found >= (self._get_config_archive_max_num_bu_before_archive_count()-1):
                self._log(msg="There were {largest_inc_file_found}/{num_bu_before_archive} backups found. We will archive and then create our base backup.".format(largest_inc_file_found=largest_inc_file_found, num_bu_before_archive=self._get_config_archive_max_num_bu_before_archive_count()-1), lvl=LogLvl.DEBUG)
                force_archive_flag = True

        # Variables that will help output timing info. Declaring here for readability
        backup_begin_time = time.time()
        backup_finished_time = 0

        if not found_base_folder:
            # No base folder found. Wipe the datadir just in case and then create our full backup
            self._wipe_bu_folder()
            self._create_full_backup()
        elif force_archive_flag:
            # We created the required number of backups so we need to archive, wipe the bu folder, and then do a full backup, and then finally try to make sure we have the correct number of archives in the archive folder
            self._archive_backups()
            self._wipe_bu_folder()
            self._create_full_backup()
            self._clean_archive_folder()
        else:
            # Base folder found, so let's create our incremental
            self._create_partial_backup(target_dir_suffix=largest_inc_file_found+1)

        backup_finished_time = time.time()
        self._log("Backup process finished in {seconds} seconds".format(seconds=backup_finished_time-backup_begin_time), lvl=LogLvl.DEBUG)
        return 0


if __name__ == '__main__':
    run = XtraBackupAutomator()
    try:
        run.log(msg="-=<>=- >>>>>>>>>>>> Entering Program <<<<<<<<<<<< -=<>=-", lvl=LogLvl.TRACE)
        run.main()
    except Exception as exc:
        run.log(msg="Program Failed Catastrophically. IN8OBX29", e=exc, lvl=LogLvl.FATAL)
        raise
    finally:
        run.log(msg="-=<>=- >>>>>>>>>>>> Exiting Program <<<<<<<<<<<< -=<>=-", lvl=LogLvl.TRACE)
