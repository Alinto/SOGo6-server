"""
File for gunicorn settings
https://docs.gunicorn.org/en/latest/configure.html#configuration-file
https://docs.gunicorn.org/en/stable/settings.html#
"""
import os

workers = int(os.environ.get("GUNICORN_WORKERS", "4"))
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "warning")


# Enable access logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log errors to stdout

access_log_format = '%(t)s: pid=%(p)s %(h)s %(l)s "%(r)s" code=%(s)s size(bytes)=%(B)s time(ms)=%(M)s "%(a)s"'
# The access log format.

# ===========  ===========
# Identifier   Description
# ===========  ===========
# h            remote address
# l            ``'-'``
# u            user name (if HTTP Basic auth used)
# t            date of the request
# r            status line (e.g. ``GET / HTTP/1.1``)
# m            request method
# U            URL path without query string
# q            query string
# H            protocol
# s            status
# B            response length
# b            response length or ``'-'`` (CLF format)
# f            referrer (note: header is ``referer``)
# a            user agent
# T            request time in seconds
# M            request time in milliseconds
# D            request time in microseconds
# L            request time in decimal seconds
# p            process ID
# {header}i    request header
# {header}o    response header
# {variable}e  environment variable
# ===========  ===========

# Use lowercase for header and environment variable names, and put
# ``{...}x`` names inside ``%(...)s``. For example::

#     %({x-forwarded-for}i)s










# backlog = 2048   #Default value is 2048 pending connections
# timeout = 30     #Default value is 30 seconds

#limit size of request see https://docs.gunicorn.org/en/stable/settings.html#security
