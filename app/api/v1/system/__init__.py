from flask_smorest import Blueprint


from.ApiSystem import blp as system_blueprint

system_apis : list[Blueprint] = [system_blueprint]
