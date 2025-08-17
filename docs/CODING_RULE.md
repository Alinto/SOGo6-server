# Coding rule

TODO, tell all the rules for uniform coding

## Naming
All names must be singular to make sure there will not be any case like this
```python
def get_mail()
def get_mails()
```
This could add reading confusion.

### Directory's name
lowercase

### file's name
#### Python files
* PascalCase if the file contains one main class. File's name must match the class
* camelCase if the files only contains utility methods and small classes.

#### Mardkwon files
Uppercase with underscore between words.

#### Other files
lowerwase

## Python

### code's case
PascalCase for Classes
Function, atribute and variable's names must be snake_case

```python
def some_func()
    some_var = 1
    return

class MyClass()
    def my_method()
        return
```
### Typing hint
Use as much as typing hint you can. The only goal os fot the IDE to know which object and which methods can be used.

To avoid import only for typing use this structure:
```python
# At the top of your file, import those two to make pylint understand the typing hint
from __future__ import annotations 
from typing import TYPE_CHECKING

from importlib import import_module # normal python import

from app.config.db.tables import ALL_TABLES # normal package import 

if TYPE_CHECKING: # Import only used for typing hint
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL
```

### import
First import external libraries
Then, relative path app libraries
Then, full path app libraries

```python
from flask import request

from app.module.preference.model.prefs import Prefs

from .schemas.userPreferences import SaveSchema, RetGetUserPreferences
```
If you need 


### Logging
Do not use `print` method, use the appropriate logger instead.

### Pylint
Pylint configuration is in `pyproject.toml` 
If pylint show a no-member error for a external modules that does exist, add the module to `generated-member` 

# SOGo parameters
If you need to add any sogo parameters/settings plus use this format
```
SOGO_{X}_{NAME}
```
* X being P, S, D or U for respectively process (ENV var and needed to start sogo), system (affects whole application), domain (affect domains) and user (affect user) settings
* NAME is the parameter name and must be uppercase snake_case
* NAME must be in english but prefers logical syntax over english syntax
    * SOGO_D_DEFAULT_EVENT_CLASS: correct english but has DEFAULT before EVENT
    * SOGO_D_EVENT_DEFAULT_CLASS: now we know this is about event and we can search SOGO_D_EVENT to see all events parameters
