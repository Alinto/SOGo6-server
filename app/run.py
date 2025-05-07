import click
from flask_compress import Compress
from flask import request
from marshmallow import ValidationError
from werkzeug.exceptions import UnprocessableEntity
from flask_wtf.csrf import CSRFError


from app import create_app, __version__

app = create_app()

@app.route("/")
def index():
    """
    Simple index, return the state, version of the backend api and link to the swagger
    """
    if app.config["DO_SWAGGER"]:
        ret = {
            "state": "running",
            "version": __version__,
            "swagger-ui": request.base_url+app.config["UI_OPENAPI_SWAGGER_UI_PATH"][1:],
            "swagger-admin": request.base_url+app.config["ADMIN_OPENAPI_SWAGGER_UI_PATH"][1:]
        }
    else:
        ret = {
            "state": "running",
            "version": __version__,
            "swagger-ui": "not deployed",
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
@click.option("--host", default="127.0.0.1")
@click.option("--port", default="5000")
@click.option("--debug/--no-debug", default=True)
@click.option("--ssl", is_flag=True)
def main(host: str, port: str, debug: bool, ssl: bool):
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
