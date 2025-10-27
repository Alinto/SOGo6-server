#bash

cd /workspace/scripts/init
curl -H 'Content-Type: application/json' -d @system_settings.json http://localhost:5000/api/adminConfig/system
curl -H 'Content-Type: application/json' -d @domain_settings.json http://localhost:5000/api/adminConfig/domain/default
