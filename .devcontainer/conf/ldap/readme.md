# Some commands

# Search all users of "ou=users,dc=example,dc=org" 

replace * by your filter like (&(mail=marko.markovic@inlocal.net)(userStatus=enabled))
`ldapsearch -D "cn=admin,dc=example,dc=org" -w password -b "ou=users,dc=example,dc=org" -s sub "*"`

# add user
`ldapadd -D "cn=admin,dc=example,dc=org" -w password -f ldifs/users.ldif`

# I don't remeber what they do...
`slapadd -F /etc/ldap/slapd.d -b cn=config -l fichier.ldif`
`slapcat -n 0 -l conf.ldif`

