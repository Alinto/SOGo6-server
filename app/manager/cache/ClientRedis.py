from json import dumps as json_dumps, loads as json_loads
from json.decoder import JSONDecodeError
from typing import cast, Type

from redis import Redis, exceptions as rexc
from redis.cache import CacheConfig
from yarl import URL

from app.utils.exceptions import AggravatedException, BugException
from app.utils import errors as err
from app.utils.logger.logger import logger_cache



class ClientRedis():
    """
    Client for redis, the cache system
    """
    #TODO fallback and timeout handling


    def __init__(self, url_str:str, resp3: bool = True):
        """
        Initialize the client.
        It's initiated with a url to avoid having a lof of parameters.
        That wats all parameters are in the query

        SOGo force the decode_responses=True.
        SOGo will use RESP3 that allow caching (needs REDIS 6.0)
        SOGo greatly encourages the use of username/password with that can only access one redis db
        Such db being only for this user/SOGo.

        SOGo use json to serialize data. The livrary picke is not safe as it will execute code.

        :param redis_url: Url for redis
        :type redis_url: str
        """
        super().__init__()

        redis_url = URL(url_str)
        redis_url = redis_url.update_query(decode_responses="Yes")
        self.cache = False
        if resp3:
            redis_url = redis_url.update_query(protocol=3)
            self.cache = True
            redis_connstring = str(redis_url)
            logger_cache.info("Setting Redis client with cache for %s", redis_connstring)
            self.redis = Redis.from_url(redis_connstring, cache_config=CacheConfig())
        else:
            redis_connstring = str(redis_url)
            logger_cache.info("Setting Redis client for %s", redis_connstring)
            self.redis = Redis.from_url(redis_connstring)

    def ping(self) -> None:
        """
        Ping to check the availability of the redis server
        """
        try:
            self.redis.ping()
        except rexc.AuthenticationError as e:
            logger_cache.error("Redis server authentication failed %s", repr(e))
            raise AggravatedException("Redis server authentication failed", err.ERROR_CACHE_AUTH_FAILED) from e
        except rexc.ConnectionError as e:
            logger_cache.error("Redis server is unavailable %s", repr(e))
            raise AggravatedException("Redis server is unavailable", err.ERROR_CACHE_NOT_REACHABLE) from e



    def set(self, key: str, value: str|list|dict, ttl: int) -> bool:
        """
        Set a key/value in the redis server

        :param key: key of the value
        :type key: str
        :param value: value to store, if not a string, will be serialize as a json before
        :type value: str | list | dict
        :param ttl: time to live of this key/value, in seconds
        :type ttl: int
        :raises BugException: Value given is not a string nor json serializable
        :return: True if the value has been successfully storeds
        :rtype: bool
        """
        if not isinstance(value, str):
            try:
                value = json_dumps(value)
            except TypeError as e:
                logger_cache.error("Data to store in cache not jsonable: %s", e)
                raise BugException("Data to store in cache not jsonable", err.ERROR_CACHE_DATA_NOT_JSON) from e

        if ttl < 1:
            #redis.set() raise redis.exceptions.ResponseError if time is 0 or less
            logger_cache.error("TTL for redis is below 1: %s", ttl)
            raise BugException(f"TTL for redis is below 1: {ttl}", err.ERROR_CACHE_TTL_BELOW_0)

        try:
            self.redis.set(name=key, value=value, ex=ttl)
        except rexc.ResponseError as e:
            logger_cache.error("Error when setting data in redis: %s", e)
            raise BugException("Error when setting data in redis", err.ERROR_CACHE_RESPONSE_ERROR) from e

        logger_cache.info("Set cached value '%s' for key '%s'", value, key)
        return True

    def get(self, key: str, expected_type: Type[str]|Type[list]|Type[dict]) -> str|list|dict|None:
        """
        Get the value stored in redis. The type of value expected must be given to be sure
        to return the correct data.

        :param key: key name of the value
        :type key: str
        :param expected_type: type of value expected
        :type expected_type: Type[str] | Type[list] | Type[dict]
        :raises BugException: If expecting a list or dict but the value is not a json
        :return: The value or None if the key does not exist.
        :rtype: str|list|dict|None
        """

        result_str = cast(str|None, self.redis.get(key))
        if result_str is not None:
            logger_cache.info("Get cached value '%s' for key '%s'", result_str, key)
            #If we expect a string directly return it
            if expected_type == str:
                return result_str

            #If we expect a list or dict, the result_str is a json
            try:
                result: list|dict = json_loads(result_str)
            except (TypeError, JSONDecodeError) as e:
                logger_cache.error("list/dict stored in redis is not a Json")
                raise BugException("list/dict stored in redis is not a Json", err.ERROR_CACHE_DATA_NOT_JSON) from e
            return result
        logger_cache.info("Get no value for key '%s'", key)
        return None

    def hashset(self, key:str, data: dict, ttl: int) -> bool:
        """
        Create or update a hash in redis.
        A hash contains a dict where value can be updated without
        giving the whole dict, only the key/value needed.
        
        (e.g. update the key last_connection for user session).

        If your dict data won't be modified, prefered set() method

        If ttl is 0 or less, the expiration will not be set or updated.

        :param key: _description_
        :type key: str
        :param data: _description_
        :type data: dict
        :param ttl: _description_
        :type ttl: int
        """

        self.redis.hset(key, mapping=data)
        if ttl > 0:
            self.redis.expire(key, ttl)
        logger_cache.info("Hashset cached value '%s' for key '%s'", data, key)
        return True

    def hashget(self, key:str) -> dict|None:
        """
        Return the whole dict of a hash

        :param key: _description_
        :type key: str
        :return: _description_
        :rtype: dict|None
        """
        ret = cast(dict|None, self.redis.hgetall(key))
        if ret:
            logger_cache.info("Hashget cached value '%s' for key '%s'", ret, key)
        else:
            logger_cache.info("Hashget no cached value for key '%s'", key)
        return ret


    def delete(self, *keys: str) -> int:
        """
        Delete all the key given

        :return: the number of deletion made
        :rtype: int
        """

        ret = cast(int, self.redis.delete(*keys))
        logger_cache.info("Delete cached value for keys '%s'", keys)

        return ret
