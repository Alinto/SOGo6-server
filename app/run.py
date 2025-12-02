import click
from flask_compress import Compress
from flask import request
from flask.typing import ResponseReturnValue
from flask_wtf.csrf import CSRFError


from app import create_app, __version__
from app.config.init_config import init_sogo


#Beware that all methods called here will be called twice because the auto-reloader is on
#To see the correct behavior run:
#poetry run start --no-debug

sogo_state: int = init_sogo()
app = create_app(sogo_state)


@app.route("/")
def index() -> ResponseReturnValue:
    """
    Simple index, return the state, version of the backend api and link to the swagger
    """
    if app.config["DO_SWAGGER"]:
        ret = {
            "state": sogo_state,
            "version": __version__,
            "swagger-sogo": request.base_url+app.config["BASIC_OPENAPI_SWAGGER_UI_PATH"][1:],
            "swagger-admin": request.base_url+app.config["ADMIN_OPENAPI_SWAGGER_UI_PATH"][1:]
        }
    else:
        ret = {
            "state": sogo_state,
            "version": __version__,
            "swagger-sogo": "not deployed",
            "swagger-admin": "not deployed"
        }
    return ret


# @app.errorhandler(CSRFError)
# def handle_csrf_error(e):
#     return "Missing scrf", 400

# @app.errorhandler(UnprocessableEntity)
# def catch_error(e: UnprocessableEntity):
#     print(type(e))
#     print(e.get_response())
#     print(e.get_body())
#     print(e.get_description())
#     return "Bad Request", 400

@click.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default="5000")
@click.option("--debug/--no-debug", default=True)
@click.option("--ssl", is_flag=True)
def main(host: str, port: int, debug: bool, ssl: bool) -> None:
    """
    Main function starting the Flask application with passed arguments.
    """

    # enable automatic request compression
    compress = Compress()
    compress.init_app(app)

    ssl_context = "adhoc" if ssl else None

    # List of arguments -> https://werkzeug.palletsprojects.com/en/stable/serving/#werkzeug.serving.run_simple
    app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
