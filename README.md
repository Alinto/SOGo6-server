<div align="center">

# SOGo 6 — API Server

**A modern wep application API (Python/Flask) for mails, calendars and addressbooks**

*An UI is also available [SOGo 6 UI](https://github.com/Alinto/SOGo6-UI), but you can use this API with scripts or even make your own UI!*


</div>

---

## WARNING

It's still an alpha in active devellopement and cannot be used in production environnement.

All features are not implemented and bugs are still presents. Changes (deprecation, rupture) may also appears on the API
and the best will be done to inform you.


## Overview

[SOGo](https://www.sogo.nu/) is an Open Source Webmail for businesses and communities. It has been arount for more that twenty years!

SOGo 6 is the new iteration with a total overhaul. SOGo 5 version can be found [here](https://github.com/Alinto/sogo).

SOGo 6 server used the python framework [Flask](https://flask.palletsprojects.com/en/stable/).

## Documentation

You can find our documentation online [here](https://www.sogo.nu/files/docs/v6)

## Prerequisites

- **Python** ≥ 3.10 (Also we're only develloping on Python 3.14, this requirement only comes from our external modules' own requirements)
- [**Poetry**](https://python-poetry.org/): ≥ 2.0 (was tested with 2.4) : Python packaging and dependency management

Some of our python modules also needs C Libraries to be installed before them:
- [python-ldap](https://www.python-ldap.org): They need the C client ldap (which was used by SOGo 5!). See their [documentation](https://www.python-ldap.org/en/latest/installing.html#build-prerequisites)
- [Psycopg](https://www.psycopg.org/psycopg3/docs/): *Beware, this is psycogpg 3, not the 2, but the apckage name is just `psycogpg`*. For the current devellopment, the pure python is used for debugging which needs the libpq PostgreSQL Client Library, see their [documentation](https://www.psycopg.org/psycopg3/docs/basic/install.html#pure-python-installation). **Even if you don't use PostgreSQL, SOGo will still install this**


## Start

In the current version, you will need to clone this repository to test SOGo 6 server.

**SOGo 6 API server** itself doesn't do a lot as it needs other services to work:

**Mandatory to start the server**
* A database server to store its data. You need a database and a user which has the rights to create table, read/writte and modify them.
* A Redis server for the caching system.

**Mandatory to authenticate**
* A user source, only ldap server for now (sql user sources are not implemented yet)

**Mandatory for mails**
* A mail server like dovecot or cyrus (all our tests has been made with dovecot)
* a outgoing mail server, postfix. (binary sendmail client not implemented yet)

### mandatory ENV or process.conf

SOGo 6 server needs process settings to make it start properly. Those process settings also included flask settings, if needed.

* You can look at the doc to see them with explanation [ProcessSetting doc](https://www.sogo.nu/files/docs/v6/SOGo6-AdminDoc/alpha/2_1_process_settings.html). The list is not completed but is enough to start.
* You can look at the [ProcessSetting.py](app/config/settings/ProcessSetting.py) to see the list
* To use a file, put it at `/etc/sogo/process.conf`. There is a example [here](.devcontainer/conf/sogo/process.conf)

### System and default domain settings

At the first run, SOGo 6 will build the databases structures but let it empty. Meaning no users source or mail server will be configured.

In this state, SOGo 6 only allows ADMIN API to set the first config.

You can avoid that by directly giving the config json files, that will only be used once. To do that, set those ENV (or in process.conf file)

* SOGO_INIT_SYSTEM_SETTINGS_PATH: string, path where to json file with system_settings
* SOGO_INIT_DOMAIN_SETTINGS_PATH: string, path where to json file with default_domain_settings

You can find example of those files there [system_settings](scripts/init/system_settings.json), [domain_settings](scripts/init/domain_settings.json) `scripts/init/system_settings.json`

* [Doc for system settings](https://www.sogo.nu/files/docs/v6/SOGo6-AdminDoc/alpha/2_2_system_settings.html)
* Doc for domain settings: Not Finish yet

### Start

Once all of this id done, use poetry to install the dependancies:

```
poetry install
```

Then you can run the Flask server:

```
poetry run start
```

*No proper gunicorn conf is provided yet, you can only run Flask in develloper mode.*

### Swaggers

At the index of the server, you will find the link to the swaggers by default, got there: `http://localhost:5000/`

## Local image

You can also build an image of SOGo with this [Dockerfile](deploy/local/Dockerfile.local).

## .Devcontainer

You can also use our devcontainer with Visual Code Studio. It will run all the external services needed.

Once build, simply run `poetry run start` to launch the Flask application.

*If you have errors about poetry, delete the file `poetry.lock` before running the devcontainer*

The swaggers will be at:
* `http://localhost:5000/swagger-basic` for the user API
* `http://localhost:5000/swagger-admin` for the Admin API


## Contributing

See **[`CONTRIBUTING.md`](./CONTRIBUTING.md)**

## License

[GPL-3.0 License](./LICENSE)