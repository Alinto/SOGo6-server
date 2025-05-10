# SOGo 6 server

## Description

Flask application which permit to publish web pages like maintenance page.

## Development

Use vscode and devcontainer will set up the development workspace.
A launcher start the project on http://localhost:5000/


## Structure

* agent/...............Contains all code of the sogo agent for event scheduling
* app/.................Contains all code of the web application
*    admin............All relative to administrator action
*    auth.............All relative to user/admin authentication
*    calendar.........All relative to Calendar, events, tasks and journal
*    common...........Common object/method among the others sections
*    contact..........All relative to Address Book and contacts
*    mail.............All relative to mail account
*    preferences......All relative to user's preferences
*    services.........All relative to services (db, redis....)
*    utils............All relative to tools and parsers
* docs................All documentation about installation, configuration and devellopers' contribution
* tests...............Contains all code for testing the web application

## Install

* for module python-ldap you'll need the openldap libraries that wont be install with poetry/pip. On debian wookworm, meanin this libldap2-dev, libsasl2-dev and ldap-utils.

