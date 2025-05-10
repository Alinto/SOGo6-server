# -*- coding: utf-8 -*-

"""
File for gunicron settings
https://docs.gunicorn.org/en/latest/configure.html#configuration-file
https://docs.gunicorn.org/en/stable/settings.html#
"""


backlog = 2048   #Default value is 2048 pending connections
bind = "127.0.0.1:8000"
timeout = 30     #Default value is 30 seconds

#limit size of request see https://docs.gunicorn.org/en/stable/settings.html#security