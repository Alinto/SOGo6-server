from math import log, ceil
from secrets import token_hex, choice
from string import ascii_letters, digits

"""
HASH Mechanism with SOGo 6

Data stored within SOGo's database generaly have a column whith a unique value.
E.g. domain_name for the table sogo6_domain_settings or uid for table sogo6_user_profiles.

This value may be needed in some API endpoint.
E.g. endpoint to get the settings of a domain.

But, such request may be log by the browser or else and we want to avoid that if the name is confidential.

We could simply use the ID of the database that auto-increment bor each new row. But, this ID
made the others row predictable.
E.g. a user with ID=3 implies that there is a user for ID=2

To avoid that we add a simple hash value as an uid for each resource row.
E.g. in the sogo6_domain_settings there is both domain_name and hash columns.
Both colums only accept unique values.

HOWEVER
We don't want to use long hash like 550e8400-e29b-41d4-a716-446655440000,
It would work but will be overpowered for table with not a lot of data.
It will also make API requests more readable.

This is wy we won't used uuid.uuid4() but secrets.token_hex(N/2) instead

with N the size of the hash which is enough to prevent colision for M entries.

To size N from M, we used the birthday attack formula
https://en.wikipedia.org/wiki/Birthday_attack

The probability of having only one collision after M hash created is:

* M is the big estimation of the number of unique row/resources (e.g; 10 000 fpr domains settings)
* n is lenght of the hash, a string with digits, lowercase, uppercase. E.g. 'a1f3b2e5' for n=8
* 62^n is the number of unique string that exist

P(collision) = 1 - exp(-M^2/2*62^n)

If we want the collision probability to be 0.01%, we get

62^n > 50*M^2

For M = 10000
we get n = 9.
Meaning that with a 9 long token, after 10000 hashes made, the chance to have two identical hashes is 0.01%
"""


#To put in SYSTEM_SETTINGS
MAX_USER   = 10000000 #10 millions user top
MAX_DOMAIN =    10000 #10 thousand domains top
MAX_RULES  =     1000 #1 rhousand rules top
MAX_ACCOUNT=  100
MAX_IDENTITY= 100

def size_hash_length(max_unique_entities: int) -> int:
    """
    Return the value n for a given M
    """
    return ceil(log(50 * max_unique_entities**2, 62))

HASH_SIZE_USER   = size_hash_length(MAX_USER)
HASH_SIZE_DOMAIN = size_hash_length(MAX_DOMAIN)
HASH_SIZE_RULES  = size_hash_length(MAX_RULES)
HASH_SIZE_ACCOUNT= size_hash_length(MAX_ACCOUNT)
HASH_SIZE_IDENTITY= size_hash_length(MAX_IDENTITY)

def get_unique_token(size: int) -> str:
    """
    :param size: _description_
    :type size: int

    """
    alphabet = ascii_letters + digits
    token = ''.join(choice(alphabet) for i in range(size))
    return token
