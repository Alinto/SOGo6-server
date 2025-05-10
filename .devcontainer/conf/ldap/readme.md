# Some commands

## Search all users of "ou=users,dc=example,dc=org" 

replace * by your filter like (&(mail=marko.markovic@inlocal.net)(userStatus=enabled))
```bash
ldapsearch -D "cn=admin,dc=example,dc=org" -w password -b "" -s sub "*"
```

## Add the users
`ldapadd -D "cn=admin,dc=example,dc=org" -w password -f ldifs/users.ldif`

## Modify a user
Simply modify the userds.ldif and recreate the container

## Modify our custom schema
- Modify custom.schema
- Go inside the container with user root:  `docker exec -it -u root sogo-openldap-1 exec`
- Execute those commands
```bash
apt update && apt install nano
cd tmp/
cp /opt/bitnami/openldap/etc/schema/custom.schema .
mkdir config
nano custom.conf
```
* In this file write:
```conf
include /opt/bitnami/openldap/etc/schema/core.schema
include /opt/bitnami/openldap/etc/schema/cosine.schema
include /opt/bitnami/openldap/etc/schema/nis.schema
include /opt/bitnami/openldap/etc/schema/inetorgperson.schema
include custom.schema
```
* Then run the commands:
```bash
slaptest -f custom.conf -F config
slapcat -F config -n0 -s cn=schema,cn=config
```
* The ouput of the last command will have the ldif like this:
```ldif
dn: cn={4}custom,cn=schema,cn=config
objectClass: olcSchemaConfig
cn: {4}custom
olcAttributeTypes: {0}( 1.3.1.6.1.4.1.12345.200.3 NAME 'myattr1' DESC 'myattr1
 ' SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 SINGLE-VALUE )
olcAttributeTypes: {1}( 1.3.6.1.4.1.12345.200.1 NAME 'myattr2' DESC 'myattr2' 
 SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 SINGLE-VALUE )
olcAttributeTypes: {2}( 1.3.6.1.4.1.12345.200.2 NAME 'myattr3' DESC 'myattr3' 
 SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 SINGLE-VALUE )
olcObjectClasses: {0}( 1.3.6.1.4.12345.600.1 NAME 'custom' DESC 'custom' AUXIL
 IARY MUST ( myattr1 $ myattr2 $ myattr3 ) )
structuralObjectClass: olcSchemaConfig
entryUUID: 43e76284-bf76-103f-9400-d5bd8650ec49
creatorsName: cn=config
createTimestamp: 20250507100327Z
entryCSN: 20250507100327.403691Z#000000#000#000000
modifiersName: cn=config
modifyTimestamp: 20250507100327Z
```
* Copy all until structuralObjectClass excluded, and paste it here in `.devcontainer/conf/ldap/schemas.custom.ldif`
* Remove all the brackets `{x}` to have somehting like this
```ldif
dn: cn=custom,cn=schema,cn=config
objectClass: olcSchemaConfig
cn: custom
olcAttributeTypes: ( 1.3.1.6.1.4.1.12345.200.3 NAME 'myattr1' DESC 'myattr1
 ' SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 SINGLE-VALUE )
olcAttributeTypes: ( 1.3.6.1.4.1.12345.200.1 NAME 'myattr2' DESC 'myattr2' 
 SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 SINGLE-VALUE )
olcAttributeTypes: ( 1.3.6.1.4.1.12345.200.2 NAME 'myattr3' DESC 'myattr3' 
 SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 SINGLE-VALUE )
olcObjectClasses: ( 1.3.6.1.4.12345.600.1 NAME 'custom' DESC 'custom' AUXIL
 IARY MUST ( myattr1 $ myattr2 $ myattr3 ) )
```
* Your new schema is ready, you can test it with the command:
```bash
ldapadd -Y EXTERNAL -H ldapi:/// -f /opt/bitnami/openldap/etc/schema/custom.ldif
```