# SOGo 6's Architecture

## app

The main app has the code for all SOGo''s webmail.
It has the API and the managers to talk with outsides services like the database or redis.

Flask app is created in `__init__.py`
Flask app is launched in `run.py`

### The fourth main parts

SOGo 6 is cut in four main parts to isolate at best their uses.


* Manager: Contains client that will talk to external services like database. Ex: SQLAlchemy to connect and execute queries to the database.
* Module: Contains Classes that will use *Manager* to read/write ressources needed. Ex: method to fetch all events between two dates with the proper manager.
* Interface: Contains class that will use one or several *Module* to fetch and fromat the data. Ex: method to fetch all events, attendees info and format all in a json.
* API: Contains all the endpoints and Flask methods. Uses *Interface* to get the data ready to send. Ex: Call an interface to get data for events between data.

That way:

* API: only contains the API code, not any functionnal code
* Module: only contains functionnal code, is unaware this is for an API. Uses manager to talk with others services which it doesn't know.
* Interface: Bridge between the API and the Module. Call differentes modules if necessary and format the data for the API.
* Manager: ARe instantiated if needed

Rules:
* 1 API call 1 Interface
* 1 Interface call 1 or more Module (ex: interface need calendar module and contact module)
* 1 Module use 0 or 1 Manager

### Special part

* Auth: Authenticate the user and get its info. Is called before reaching the endpoint with flask's wrapper @before_request
* Conf: Get the config for SOGo6, and the config associated to the domain and user after auth. Is called before reaching the endpoint with flask's wrapper @before_request
* Utils: contains some utility methods

* User and Config info are propagated through API, Interface and Module.

### Inside a part

Inside *api*, *interface* and *module* are found these directories:
* admin: all concerning admin api
* calendar: all concerning calendar part
* contact: all concerning contact part
* mail: all concerning mail part
* preference: all concerning user's preference