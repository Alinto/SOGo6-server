from app.utils.db.Table import Column, Table



COL_ID   = Column(name="id", data_type="serial") #No need to set is_unique=True for this one
COL_HASH = Column(name="hash", data_type="str", is_unique=True)

##############################
# Table sogo_settings_system #
##############################
"""
Only one query to fecth all
SELECT TOP 1 * from sogo_settings WHERE id = 1;
"""
# settings_unique is just a watchguard to make sure there is only one row in this table
# settings_system: sogo's system settings
# settings_domain_default: sogo's domain default settings
COL_SETTINGS_UNIQUE         = Column(name="settings_unique", data_type="int8")
COL_SETTINGS_SYSTEM         = Column(name="settings_system", data_type="dict")
COL_SETTINGS_DOMAIN_DEFAULT = Column(name="settings_domain_default", data_type="dict")
ALL_SETTINGS_COL            = [COL_SETTINGS_UNIQUE,
                               COL_SETTINGS_SYSTEM,
                               COL_SETTINGS_DOMAIN_DEFAULT]
TABLE_SETTINGS = Table(name="sogo_settings", columns=ALL_SETTINGS_COL, primary_keys=(COL_SETTINGS_UNIQUE.name,))

###############################
# Table sogo_settings_domains #
###############################
"""
Query to fecth the settings from a domain for every authenticated API request
SELECT domain_settings from sogo_settings_domains WHERE domain_name = <domain>;

Query to fetch the settings and their origins for the config interface
SELECT domain_settings,domain_origin from sogo_settings_domains WHERE domain_name = <domain>;
"""
# domain_name: Name of the domain
# domain_description: Description of the domain if needed
# domain_info: Info for this domain
# domain_settings: Settings of this domain
# domain_origin: Origin of the tsettings (default sogo, default admin, rule's name or direct)
# domain_user_defaults: all user settings with value force by the admin
COL_DOMAIN_NAME          = Column(name="domain_name", data_type="str", extra_args={"max_len": 255}, is_unique=True) #max length is 255 -> https://www.rfc-editor.org/rfc/rfc1035#section-2.3.4
COL_DOMAIN_DESCRIPTION   = Column(name="domain_description", data_type="str", is_nullable=True)
COL_DOMAIN_INFO          = Column(name="domain_info", data_type="str", is_nullable=True)
COL_DOMAIN_SETTINGS      = Column(name="domain_settings", data_type="dict")
COL_DOMAIN_ORIGIN        = Column(name="domain_origins", data_type="dict")
COL_DOMAIN_USER_DEFAULTS = Column(name="domain_user_defaults", data_type="dict")
ALL_DOMAIN_COL           = [COL_ID,
                            COL_HASH,
                            COL_DOMAIN_NAME,
                            COL_DOMAIN_DESCRIPTION,
                            COL_DOMAIN_INFO,
                            COL_DOMAIN_SETTINGS,
                            COL_DOMAIN_ORIGIN]
TABLE_DOMAIN = Table(name="sogo_settings_domains", columns=ALL_DOMAIN_COL, primary_keys=(COL_ID.name, COL_HASH.name, COL_DOMAIN_NAME.name))

#############################
# Table sogo_settings_rules #
#############################
"""
Query to fecth the settings from a domain for every authenticated API request
SELECT domain_settings from sogo_settings_domains WHERE domain_name = <domain>;

Query to fect hthe settings and their origins for the config interface
SELECT domain_settings,domain_origin from sogo_settings_domains WHERE domain_name = <domain>;
"""
# rule_name: Name of the rule
# rule_description: Description of the rule
# rule_domains: domains affected by this rule
# rule_setting: Settings affected by this rule
COL_RULE_NAME        = Column(name="rule_name", data_type="str", is_unique=True, extra_args={"max_len": 255})
COL_RULE_DESCRIPTION = Column(name="rule_description", data_type="str")
COL_RULE_DOMAINS     = Column(name="rule_domains", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 255}})
COL_RULE_SETTINGS    = Column(name="rule_setting", data_type="dict")
ALL_RULE_COL      = [COL_ID,
                     COL_HASH,
                     COL_RULE_NAME,
                     COL_RULE_DOMAINS,
                     COL_RULE_SETTINGS]
TABLE_RULES = Table(name="sogo_settings_rules", columns=ALL_RULE_COL, primary_keys=(COL_ID.name, COL_HASH.name, COL_RULE_NAME.name))

#############################
# Table sogo_user_profiles #
#############################
"""
All queries will have WHERE uid = <uid>
"""
# uid: full email of the user, even if the login is domainless
# identities: Identities and signature of this user
# folders: folders id and name for this user
# filters: sieve filters of this user
# preferences: user settings
# private_salt: unique salt generated for the user.
# acl_given: acl given to users
# acl_received: acl received from users
# delegation_given: delegtation given to users
# delegation_received: delegtation received from users
COL_USER_UID              = Column(name="uid", data_type="str", extra_args={"max_len": 512}, is_unique=True)
COL_USER_DEFAULTS         = Column(name="preferences", data_type="dict")
COL_USER_FOLDERS          = Column(name="folders", data_type="dict")
COL_USER_IDENTITIES       = Column(name="identities", data_type="dict")
COL_USER_FILTERS          = Column(name="filters", data_type="dict", is_nullable=True)
COL_USER_PRIVATE_SALT     = Column(name="private_salt", data_type= "str", extra_args={"max_len": 4096})
COL_USER_ACL_GIVEN        = Column(name="acl_given", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
COL_USER_ACL_GOT          = Column(name="acl_received", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
COL_USER_DELEGATION_GIVEN = Column(name="delegation_given", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
COL_USER_DELEGATION_GOT   = Column(name="delegation_received", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
ALL_USER_COL              = [COL_ID,
                             COL_HASH,
                             COL_USER_UID,
                             COL_USER_DEFAULTS,
                             COL_USER_FOLDERS,
                             COL_USER_IDENTITIES,
                             COL_USER_FILTERS,
                             COL_USER_PRIVATE_SALT,
                             COL_USER_ACL_GIVEN,
                             COL_USER_ACL_GOT,
                             COL_USER_DELEGATION_GIVEN,
                             COL_USER_DELEGATION_GOT]
TABLE_USER = Table(name="sogo_user_profiles", columns=ALL_USER_COL, primary_keys=(COL_ID.name, COL_HASH.name, COL_USER_UID.name,))



ALL_TABLES = [TABLE_SETTINGS,
              TABLE_DOMAIN,
              TABLE_RULES,
              TABLE_USER]
