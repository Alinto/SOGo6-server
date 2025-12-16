#Start error
ERROR_NO_ERRROR        = "S000000"
ERROR_SOGO_INIT        = "S000001"
ERROR_SOGO_WRONG_STATE = "S000002"
ERROR_API_NOT_JSON     = "S000003"
ERROR_API_CONTENT_TYPE = "S000004"

#API
ERROR_VALIDATION_ERROR = "S000300"
ERROR_DOMAIN_NAME_TAKEN = "S000301"
ERROR_DOMAIN_NAME_NOT_FOUND = "S000302"

ERROR_MAIL_UID_NOT_FOUND = "S000303"
ERROR_FOLDER_NAME_NOT_FOUND = "S000304"

ERROR_IMAP_UNAUTHORIZED = "S000310"
ERROR_IMAP_CONNECTION_FAILED = "S000311"
ERROR_MAILBOX_NOT_FOUND = "S000312"
ERROR_INVALID_CREDENTIALS = "S000313"

#Database
ERROR_BUG_UNKNWON_TABLE = "S000400"
ERROR_BUG_UNKNWON_COLUMN = "S000401"
ERROR_BUG_UNKNWON_ORDER = "S000402"
ERROR_QUERY_DELETION_ROWS = "S000403"
ERROR_QUERY_DELETION_CONDITION = "S000404"

#
ERROR_TABLE_SYSTEM_NOT_UNIQUE = "S000600"

ERROR_UNKOWN = "S999999"

error_msg = {
    ERROR_NO_ERRROR: "",
    ERROR_SOGO_INIT: "Sogo is not initiated",
    ERROR_SOGO_WRONG_STATE: "Sogo is in an unknwon state and can't start",
    ERROR_API_NOT_JSON: "Request POST/PATCH/PUT data is not a json",
    ERROR_API_CONTENT_TYPE: "Request POST/PATCH/PUT Content-Type is not application/json",

    ERROR_VALIDATION_ERROR: "Data given does not match the Marshmallow Schema",
    ERROR_DOMAIN_NAME_TAKEN: "Domain's name already taken",
    ERROR_DOMAIN_NAME_NOT_FOUND: "Domain name not found in database",

    ERROR_MAIL_UID_NOT_FOUND: "Mail UID not found",
    ERROR_FOLDER_NAME_NOT_FOUND: "Folder name not found",
    ERROR_IMAP_UNAUTHORIZED: "IMAP unauthorized - invalid credentials or insufficient permissions",
    ERROR_IMAP_CONNECTION_FAILED: "IMAP connection failed",
    ERROR_MAILBOX_NOT_FOUND: "Mailbox not found",
    ERROR_INVALID_CREDENTIALS: "Invalid credentials provided",

    ERROR_BUG_UNKNWON_TABLE: "Trying to interact with an unkwnon table",
    ERROR_BUG_UNKNWON_COLUMN: "Trying to interact with an unkwnon column",
    ERROR_BUG_UNKNWON_ORDER: "Trying to order in a unknown order",
    ERROR_QUERY_DELETION_ROWS: "Conditon to delete query affect more or less rows than expected",
    ERROR_QUERY_DELETION_CONDITION: "Conditon to delete query is always true",

    ERROR_TABLE_SYSTEM_NOT_UNIQUE: "TABLE_SETTINGS is not unique as it shoul be",

    ERROR_UNKOWN: "Error has not been defined",
}


#HTTP Status Code mapping for error codes
#TODO: implementer ces codes dans error_msg et dans les modules/managers?
error_http_status = {
    # 400 - Bad Request (validation, malformed data)
    ERROR_VALIDATION_ERROR: 400,
    ERROR_API_NOT_JSON: 400,
    ERROR_API_CONTENT_TYPE: 400,
    ERROR_SOGO_INIT: 400,
    ERROR_SOGO_WRONG_STATE: 400,

    # 401 - Unauthorized (authentication failures)
    ERROR_IMAP_UNAUTHORIZED: 401,
    ERROR_INVALID_CREDENTIALS: 401,

    # 404 - Not Found (resource doesn't exist)
    ERROR_DOMAIN_NAME_NOT_FOUND: 404,
    ERROR_MAIL_UID_NOT_FOUND: 404,
    ERROR_FOLDER_NAME_NOT_FOUND: 404,
    ERROR_MAILBOX_NOT_FOUND: 404,

    # 409 - Conflict (resource already exists)
    ERROR_DOMAIN_NAME_TAKEN: 409,

    # 500 - Internal Server Error (bugs, unexpected errors)
    ERROR_BUG_UNKNWON_TABLE: 500,
    ERROR_BUG_UNKNWON_COLUMN: 500,
    ERROR_BUG_UNKNWON_ORDER: 500,
    ERROR_QUERY_DELETION_ROWS: 500,
    ERROR_QUERY_DELETION_CONDITION: 500,
    ERROR_TABLE_SYSTEM_NOT_UNIQUE: 500,
    ERROR_UNKOWN: 500,

    # 503 - Service Unavailable (connection failures)
    ERROR_IMAP_CONNECTION_FAILED: 503,
}
