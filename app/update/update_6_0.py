from app.config.db import tables as tbl
from app.config.settings.ProcessSetting import process_config
from app.module.common_module import get_sogo6_database


def update() -> None:
    sogo_db_manager = get_sogo6_database(process_config)
    sogo_db_manager.add_column(tbl.TABLE_DOMAIN, tbl.COL_DOMAIN_DESCRIPTION)
    sogo_db_manager.modify_column(tbl.TABLE_DOMAIN, tbl.COL_DOMAIN_INFO)
    sogo_db_manager.close()