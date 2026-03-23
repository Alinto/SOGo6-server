from http import HTTPStatus

class E:
    """
    Class to represent a SOGo 6 API error.

    A SOGo 6 API error has three attributes:
    - a string code 'S' + 6 numbers
    - a readable human message
    - a http code status if needed (no every error means to has a http response)
    """
    _all_codes: set = set()

    def __init__(self, c:str, m:str, h:int = HTTPStatus.INTERNAL_SERVER_ERROR):
        """
        Error representation of SOGo 6

        h, the http code status is used to differentiate the same type of RequestException
        that may needs to return a different code.

        :param c: code of the error (S000001)
        :type c: str
        :param m: human message of this error
        :type m: str
        :param h: If relevant, http code status that should be return for this error, defaults to 500
        :type h: int, optional
        :raises ValueError: if code already taken or not conform
        """
        if c in self._all_codes:
            raise ValueError(f"Error code {c} already set")
        if len(c) != 7 or c[0] != 'S':
            raise ValueError(f"Error code {c} not conform ('S' + 6 numbers)")
        self._all_codes.add(c)
        self.c = c
        self.m = m
        self.h = h

#Start error
ERROR_NO_ERROR               = E("S000000", "No Error", HTTPStatus.OK)
ERROR_SOGO_INIT               = E("S000001", "Sogo Has Not Been Configured Yet", HTTPStatus.PRECONDITION_FAILED)
ERROR_SOGO_WRONG_STATE        = E("S000002", "Sogo Is In An Unknwon State And Can't Start", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_CACHE_NOT_REACHABLE     = E("S000005", "Cache Server Is Unreachable", HTTPStatus.PRECONDITION_FAILED)
ERROR_CACHE_AUTH_FAILED       = E("S000006", "Cache Server Authentication Failed", HTTPStatus.PRECONDITION_FAILED)
ERROR_TABLE_SYSTEM_NOT_UNIQUE = E("S000007", "Sogo Table For System Settings Is Not Unique", HTTPStatus.PRECONDITION_FAILED)

#General Error
ERROR_CONFIG_ERROR = E("S000020", "A configuration Problem prevent SOGo to work properly", HTTPStatus.INTERNAL_SERVER_ERROR)

#CACHE
ERROR_CACHE_DATA_NOT_JSON  = E("S000100", "Cache Server Data Is Not A Json", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_CACHE_TTL_BELOW_0    = E("S000101", "Cache Server Data TTL Is Below 1", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_CACHE_RESPONSE_ERROR = E("S000102", "Cache Server Response Error", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_CACHE_SCAN_FAILED    = E("S000103", "Cache Server Scan Failed", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_CACHE_REVOKE_FAILED  = E("S000104", "Cache Server Session Revocation Failed", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_CACHE_REVOKE_KEY_FAILED = E("S000105", "Cache Server Session Revocation By Key Failed", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_REVOKE_BODY_INVALID  = E("S000106", "Revoke Request Must Contain Exactly One Of 'uid' Or 'redis_key'", HTTPStatus.BAD_REQUEST)


#LOGIN
ERROR_LOGIN_NO_DOMAIN          = E("S000200", "Login Is Domainless. See SOGO_S_DOMAINLESS_LOGIN", HTTPStatus.BAD_REQUEST)
ERROR_LOGIN_DOMAIN_UNKNOWN     = E("S000201", "Login With Unknown Domain. See SOGO_S_REJECT_UNKNOWN_DOMAIN and SOGO_S_KNOWN_DOMAIN", HTTPStatus.BAD_REQUEST)
ERROR_WRONG_AUTHORIZATION_TYPE = E("S000202", "Header Authorization Incorrect Format", HTTPStatus.UNAUTHORIZED)
ERROR_AUTHENTICATED_ROUTE      = E("S000203", "Anonymous User On Protected Endpoint", HTTPStatus.UNAUTHORIZED)
ERROR_API_NOT_JSON             = E("S000204", "Request POST/PATCH/PUT Body Is Not A Json", HTTPStatus.BAD_REQUEST)
ERROR_API_CONTENT_TYPE         = E("S000205", "Request POST/PATCH/PUT Content-Type Is Not 'application/json'", HTTPStatus.BAD_REQUEST)
ERROR_VALIDITY_TIME_BELOW_0    = E("S000206", "Voucher Validity Time Below 0", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_USER_CREDS_NOT_VALID     = E("S000207", "User credentials stores in session are not valid anymore", HTTPStatus.UNAUTHORIZED)


#API
ERROR_VALIDATION_ERROR      = E("S000300", "Request Data Incorrect Format", HTTPStatus.BAD_REQUEST)
ERROR_DOMAIN_NAME_TAKEN     = E("S000301", "Domain's Name Already Taken", HTTPStatus.BAD_REQUEST)
ERROR_DOMAIN_NAME_NOT_FOUND = E("S000302", "Domain's Name Not Found", HTTPStatus.NOT_FOUND)

ERROR_MAIL_UID_NOT_FOUND    = E("S000303", "Mail's UID Not Found", HTTPStatus.NOT_FOUND)
ERROR_FOLDER_NAME_NOT_FOUND = E("S000304", "Folder's Name Not Found", HTTPStatus.NOT_FOUND)
ERROR_FOLDER_ALREADY_EXIST  = E("S000305", "Folder already exist", HTTPStatus.CONFLICT)
ERROR_FOLDER_CANNOT_RENAME  = E("S000306", "Folder cannot be renamed", HTTPStatus.BAD_REQUEST)
ERROR_FOLDER_NOT_UNIQUE     = E("S000307", "Folder is not unique", HTTPStatus.CONFLICT)
ERROR_FOLDER_DELIMITER      = E("S000308", "Cannot create a folder with delimiter in the name", HTTPStatus.BAD_REQUEST)
ERROR_INVALID_ACTION         = E("S000309", "Invalid Action Specified", HTTPStatus.BAD_REQUEST)
ERROR_MISSING_ACTION_DATA    = E("S001306", "Missing Required Data For Action", HTTPStatus.BAD_REQUEST)

ERROR_IMAP_UNAUTHORIZED      = E("S000310", "IMAP Unauthorized - Invalid Credentials Or Insufficient Permissions", HTTPStatus.UNAUTHORIZED)
ERROR_IMAP_CONNECTION_FAILED = E("S000311", "IMAP connection failed", HTTPStatus.SERVICE_UNAVAILABLE)
ERROR_MAILBOX_NOT_FOUND      = E("S000312", "Mailbox Not Found", HTTPStatus.NOT_FOUND)
ERROR_MAIL_DELETION          = E("S000313", "Mail Deletion Error", HTTPStatus.BAD_REQUEST)
ERROR_IMAP_LOGOUT            = E("S001300", "Try To Make An IMAP Command While Being In LOGOUT state", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_IMAP_UNAIVALABLE       = E("S001301", "IMAP Command Failed Momenteraly, Try Again Later", HTTPStatus.SERVICE_UNAVAILABLE)
ERROR_IMAP_FAILED            = E("S001302", "IMAP Command Failed, See Logs To Get More Details", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_IMAP_UNKNWON_AUTH_MECH = E("S001303", "IMAP Auth Mechanism Unknown", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_IMAP_NOT_ASCII         = E("S001304", "Name for imap command is not ascii", HTTPStatus.BAD_REQUEST)
ERROR_IMAP_READONLY          = E("S001305", "Writting Command to a readonly folder", HTTPStatus.INTERNAL_SERVER_ERROR)

ERRRIR_MAIL_DELETION         = E("S001313", "Mail Deletion Error", HTTPStatus.BAD_REQUEST)
ERROR_MAIL_DOWNLOAD_FAILED   = E("S000360", "Mail Download Failed", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_MAIL_ZIP_FAILED        = E("S000361", "Mail Zip Archive Creation Failed", HTTPStatus.INTERNAL_SERVER_ERROR)

#User Profile
ERROR_USER_PROFILE_DUPLICATE         = E("S000314", "Multiple User Profiles Found For Same UID", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_USER_PROFILE_CREATION_FAILED   = E("S000315", "User Profile Creation Failed", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_USER_PROFILE_INSERT_MISMATCH   = E("S000316", "User Profile Insert Row Count Mismatch", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_USER_PROFILE_NOT_FOUND         = E("S000317", "User Profile Not Found", HTTPStatus.NOT_FOUND)
ERROR_USER_PROFILE_UPDATE_FAILED     = E("S000318", "User Profile Update Failed", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_USER_PROFILE_NO_IDENTITY       = E("S000319", "Account must have at least one identity", HTTPStatus.BAD_REQUEST)
ERROR_USER_PROFILE_MISMATCH_CLASS_DB = E("S000326", "User profile colums differentiate from UserProfile class attributes", HTTPStatus.INTERNAL_SERVER_ERROR)

#External Accounts
ERROR_EXTERNAL_ACCOUNT_NOT_FOUND    = E("S000320", "External Account Not Found", HTTPStatus.NOT_FOUND)
ERROR_EXTERNAL_ACCOUNT_HASH_CONFLICT= E("S000321", "External Account Hash Conflict", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_EXTERNAL_ACCOUNT_INVALID_DATA = E("S000322", "External Account Invalid Data", HTTPStatus.BAD_REQUEST)
ERROR_EXTERNAL_ACCOUNT_ALREADY_EXISTS = E("S000323", "External Account Already Exists", HTTPStatus.BAD_REQUEST)

#Main Account
ERROR_MAIN_ACCOUNT_NOT_FOUND = E("S000324", "Main Account Not Found", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_MAIN_ACCOUNT_CANNOT_BE_DELETED = E("S000325", "Main Account Cannot Be Deleted", HTTPStatus.FORBIDDEN)


#Domain Restrictions
ERROR_EXTERNAL_ACCOUNT_FORBIDDEN = E("S000330", "External account creation is forbidden for your domain", HTTPStatus.FORBIDDEN)
ERROR_IDENTITIES_FORBIDDEN = E("S000331", "Multiple identities are forbidden in your main account for your domain", HTTPStatus.FORBIDDEN)
ERROR_IDENTITIES_CUSTOM_FROM_FORBIDDEN = E("S000332", "Custom 'from' email in identities is forbidden for your domain", HTTPStatus.FORBIDDEN)
ERROR_IDENTITIES_CUSTOM_NAME_FORBIDDEN = E("S000333", "Custom name in identities is forbidden for your domain", HTTPStatus.FORBIDDEN)
ERROR_IDENTITIES_CUSTOM_REPLY_TO_FORBIDDEN = E("S000334", "Custom reply-to email in identities is forbidden for your domain", HTTPStatus.FORBIDDEN)
ERROR_SIGNATURE_SIZE_EXCEEDED = E("S000335", "Signature size exceeds the maximum allowed limit for your domain", HTTPStatus.FORBIDDEN)

#Preferences
ERROR_PREF_UNKNOWN_SUB = E("S000340", "Subparent of User Settings does not exist", HTTPStatus.BAD_REQUEST)

#Delegations
ERROR_DELEGATION_NOT_FOUND = E("S000350", "Delegation Not Found", HTTPStatus.NOT_FOUND)
ERROR_DELEGATION_ALREADY_EXISTS = E("S000351", "Delegation Already Exists", HTTPStatus.BAD_REQUEST)
ERROR_DELEGATION_INVALID_EMAIL = E("S000352", "Invalid Email Address For Delegation", HTTPStatus.BAD_REQUEST)

#Database
ERROR_BUG_UNKNWON_TABLE        = E("S000400", "Database Unknown Table", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_BUG_UNKNWON_COLUMN       = E("S000401", "Database Unknown Column", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_BUG_UNKNOWN_ORDER        = E("S000402", "Database Unknown Order Name", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_QUERY_DELETION_ROWS      = E("S000403", "Database Deletion Query Is Unexpected", HTTPStatus.INTERNAL_SERVER_ERROR)
ERROR_QUERY_DELETION_CONDITION = E("S000404", "Database Deletion Query Delete Everything", HTTPStatus.INTERNAL_SERVER_ERROR)

#Config
ERROR_CONFIG_WRONG_MAIL_SERVER = E("S000500", "Mail server type is unknown or not supported", HTTPStatus.INTERNAL_SERVER_ERROR)

#the bugs
ERROR_UNKOWN = E("S999999", "Undefined Error", HTTPStatus.INTERNAL_SERVER_ERROR)
