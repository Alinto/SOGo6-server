
#Start error
ERROR_NO_ERRROR        = 0
ERROR_SOGO_INIT        = 1
ERROR_SOGO_WRONG_STATE = 2
ERROR_API_NOT_JSON     = 3
ERROR_API_CONTENT_TYPE = 4

#API
ERROR_VALIDATION_ERROR = 300
ERROR_DOMAIN_NAME_TAKEN = 301
ERROR_DOMAIN_NAME_NOT_FOUND = 302

#Database
ERROR_BUG_UNKNWON_TABLE = 400
ERROR_BUG_UNKNWON_COLUMN = 401
ERROR_BUG_UNKNWON_ORDER = 402
ERROR_QUERY_DELETION_ROWS = 403
ERROR_QUERY_DELETION_CONDITION = 404

#
ERROR_TABLE_SYSTEM_NOT_UNIQUE = 600

ERROR_UNKOWN = 99999

error_msg = {
    ERROR_NO_ERRROR: "",
    ERROR_SOGO_INIT: "Sogo is not initiated",
    ERROR_SOGO_WRONG_STATE: "Sogo is in an unknwon state and can't start",
    ERROR_API_NOT_JSON: "Request POST/PATCH/PUT data is not a json",
    ERROR_API_CONTENT_TYPE: "Request POST/PATCH/PUT Content-Type is not application/json",

    ERROR_VALIDATION_ERROR: "Data given does not match the Marshmallow Schema",
    ERROR_DOMAIN_NAME_TAKEN: "Domain's name already taken",
    ERROR_DOMAIN_NAME_NOT_FOUND: "Domain name not found in database",

    ERROR_BUG_UNKNWON_TABLE: "Trying to interact with an unkwnon table",
    ERROR_BUG_UNKNWON_COLUMN: "Trying to interact with an unkwnon column",
    ERROR_BUG_UNKNWON_ORDER: "Trying to order in a unknown order",
    ERROR_QUERY_DELETION_ROWS: "Conditon to delete query affect more or less rows than expected",
    ERROR_QUERY_DELETION_CONDITION: "Conditon to delete query is always true",

    ERROR_TABLE_SYSTEM_NOT_UNIQUE: "TABLE_SETTINGS is not unique as it shoul be",

    ERROR_UNKOWN: "Error has not been defined",
}
