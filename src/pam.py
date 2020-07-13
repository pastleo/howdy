# PAM interface in python, launches compare.sh

# Import required modules
import subprocess
import os
import glob
import syslog
import time

# pam-python is running python 2, so we use the old module here
import ConfigParser

# Read config from disk
config = ConfigParser.ConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__)) + "/config.ini")

def doAuth(pamh):
	"""Starts authentication in a seperate process"""

	# Abort is Howdy is disabled
	if config.getboolean("core", "disabled"):
		return pamh.PAM_AUTHINFO_UNAVAIL

	# Abort if we're in a remote SSH env
	if config.getboolean("core", "ignore_ssh"):
		if "SSH_CONNECTION" in os.environ or "SSH_CLIENT" in os.environ or "SSHD_OPTS" in os.environ:
			return pamh.PAM_AUTHINFO_UNAVAIL

	# Abort if lid is closed
	if config.getboolean("core", "ignore_closed_lid"):
		if any("closed" in open(f).read() for f in glob.glob("/proc/acpi/button/lid/*/state")):
			return pamh.PAM_AUTHINFO_UNAVAIL

	# Set up syslog
	syslog.openlog("[HOWDY]", 0, syslog.LOG_AUTH)

	# Alert the user that we are doing face detection
	if config.getboolean("core", "detection_notice"):
		pamh.conversation(pamh.Message(pamh.PAM_TEXT_INFO, "Attempting face detection"))

	syslog.syslog("Attempting facial authentication for user " + pamh.get_user())

	# Run compare using sudo and python3 subprocess to circumvent python version, import and permission issues

	# original python3 command:
	# subprocess.call(["/usr/bin/python3", os.path.dirname(os.path.abspath(__file__)) + "/compare.py", pamh.get_user()])

	status_file_rand = "{}".format(time.time())
	status_file_path = "/tmp/howdy-compare-{}".format(status_file_rand)

	sudo_status = subprocess.call(["sudo", "-E", os.path.dirname(os.path.abspath(__file__)) + "/compare.sh", pamh.get_user(), status_file_rand])

	if sudo_status != 0:
		pamh.conversation(pamh.Message(pamh.PAM_TEXT_INFO, "sudo failed"))
		syslog.syslog("[HOWDY] Failure, sudo error" + str(sudo_status))
		return pamh.PAM_SYSTEM_ERR

	status_file = open(status_file_path)
	status = int(status_file.read().strip())
	status_file.close()

	# Status 10 means we couldn't find any face models
	if status == 10:
		if not config.getboolean("core", "suppress_unknown"):
			pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "No face model known"))

		syslog.syslog("Failure, no face model known")
		syslog.closelog()
		return pamh.PAM_USER_UNKNOWN

	# Status 11 means we exceded the maximum retry count
	elif status == 11:
		pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "Face detection timeout reached"))
		syslog.syslog("Failure, timeout reached")
		syslog.closelog()
		return pamh.PAM_AUTH_ERR

	# Status 12 means we aborted
	elif status == 12:
		syslog.syslog("Failure, general abort")
		syslog.closelog()
		return pamh.PAM_AUTH_ERR

	# Status 13 means the image was too dark
	elif status == 13:
		syslog.syslog("Failure, image too dark")
		syslog.closelog()
		pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "Face detection image too dark"))
		return pamh.PAM_AUTH_ERR
	# Status 0 is a successful exit
	elif status == 0:
		# Show the success message if it isn't suppressed
		if not config.getboolean("core", "no_confirmation"):
			pamh.conversation(pamh.Message(pamh.PAM_TEXT_INFO, "Identified face as " + pamh.get_user()))

		syslog.syslog("Login approved")
		syslog.closelog()
		return pamh.PAM_SUCCESS

	# Otherwise, we can't discribe what happend but it wasn't successful
	pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "Unknown error: " + str(status)))
	syslog.syslog("Failure, unknown error" + str(status))
	syslog.closelog()
	return pamh.PAM_SYSTEM_ERR


def pam_sm_authenticate(pamh, flags, args):
	"""Called by PAM when the user wants to authenticate, in sudo for example"""
	return doAuth(pamh)


def pam_sm_open_session(pamh, flags, args):
	"""Called when starting a session, such as su"""
	return doAuth(pamh)


def pam_sm_close_session(pamh, flags, argv):
	"""We don't need to clean anyting up at the end of a session, so returns true"""
	return pamh.PAM_SUCCESS


def pam_sm_setcred(pamh, flags, argv):
	"""We don't need set any credentials, so returns true"""
	return pamh.PAM_SUCCESS
