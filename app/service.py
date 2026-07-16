from app.config.settings.ProcessSetting import process_config
from app.manager.agent.ClientAgent import ClientAgent
from app.manager.cache.ClientRedis import ClientRedis
from app.utils import exceptions as exc

cache_client: ClientRedis|None = None
agent_client: ClientAgent|None = None

def sogo_cache() -> ClientRedis:
    """
    Return the cache client if not None.
    The file run.py is supposed set cache_client with the correct instance.

    Using this method instead of "from app import cache_client" avoid the warning
    for potential None value.
    """
    #TODO there is a bug with one instance of the client, fallbacl to instaniate each time
    # if isinstance(cache_client, ClientRedis):
    #     return cache_client
    
    #Init a fresh redis client each time
    redis_conf = process_config.get_redis_settings()
    return ClientRedis(**redis_conf)
    raise exc.AggravatedException("Cache not instantiated when needed")

def set_cache(new_cache: ClientRedis) -> None:
    """
    Set the cache, will be the same for all requests of this worker
    """
    global cache_client # pylint: disable=global-statement
    cache_client = new_cache

def sogo_agent() -> ClientAgent:
    """Return the agent client. Set by ``run.py`` at process start."""
    if isinstance(agent_client, ClientAgent):
        return agent_client
    raise exc.AggravatedException("Agent client not instantiated when needed")

def set_agent(new_client: ClientAgent) -> None:
    """Set the agent client, shared by all requests of this worker."""
    global agent_client # pylint: disable=global-statement
    agent_client = new_client
