from os import access, path, makedirs, W_OK

from logging import basicConfig, getLogger, handlers
from logging import DEBUG, INFO, WARNING, ERROR


# LOG_DIR = "/var/log/sogo"
# LOG_FILE = f"{LOG_DIR}/sogo.log"

# def create_log_dir(log_directory):
#     """Create log directory if it doesn't exist."""
#     if not path.isdir(log_directory):
#         try:
#             makedirs(log_directory)
#             return True
#         except Exception as e:
#             print(f"Error : impossible to create the logging directory {e}")
#             return False
#     return True

# def check_permission_dir(log_directory):
#     """Check if it's possible to write in this directory."""
#     if not access(log_directory, W_OK):
#         print("Error : no permission to write in the logging directory %s \n\t=> no log file"%log_directory)
#         return  False
#     return True

# def check_permission_file(filename):
#     """Check if it's possible to write in file."""
#     if path.isfile(filename) and not access(filename, W_OK):
#         print("Error : no permission to write in the logging file %s \n\t=> no log file"%filename)
#         return False
#     return True

# create_log_dir(LOG_DIR)
# check_permission_dir(LOG_DIR)
# check_permission_dir(LOG_FILE)


LOG_FORMAT = "%(asctime)s [%(levelname)s][%(name)s][%(filename)s:%(funcName)s:%(lineno)d]: %(message)s"
basicConfig(format=LOG_FORMAT, level=DEBUG)

# file_handler = handlers.RotatingFileHandler()

logger            = getLogger("sogolog")
logger_api        = getLogger("sogolog.api")
logger_usersource = getLogger("sogolog.usersource")
logger_config     = getLogger("sogolog.config")
logger_auth       = getLogger("sogolog.auth")
logger_sql        = getLogger("sogolog.sql")
logger_imap       = getLogger("sogolog.imap")
logger_sieve      = getLogger("sogolog.sieve")
logger_cache      = getLogger("sogolog.cache")
logger_mail_server = getLogger("sogolog.mailserver")
logger_mail_outgoing = getLogger("sogolog.mailoutgoing")
logger_user_profile = getLogger("sogolog.userprofile")
logger_calendar = getLogger("sogolog.calendar")
logger_agent = getLogger("sogolog.agent")
logger_contact = getLogger("sogolog.contact")

logger_sql.setLevel(ERROR)
logger_cache.setLevel(ERROR)
