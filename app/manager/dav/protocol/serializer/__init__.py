"""Serializers of the DAV messages, from and to XML.

ElementTree keeps its namespace prefixes in a registry shared by the whole process. They are registered once,
when the package is loaded, before any of its serializers: registering them at each serialization would
change the registry under concurrent ones.
"""

from xml.etree.ElementTree import register_namespace

from app.manager.dav.protocol.DavProtocolConst import NS_PREFIXES

for _prefix, _namespace in NS_PREFIXES.items():
    register_namespace(_prefix, _namespace)
