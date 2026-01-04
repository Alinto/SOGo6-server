#bash

cd /workspace/scripts/init
curl -X PATCH -H 'Content-Type: application/json' -d @system_settings.json http://localhost:5000/api/admin/v1/config/system
curl -X PATCH -H 'Content-Type: application/json' -d @domain_settings.json http://localhost:5000/api/admin/v1/config/domain-default
