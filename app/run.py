import click
from flask_compress import Compress

from app import create_app, __version__
from app.config_sogo import config

app = create_app()

@app.route("/")
def index():
    """
    Simple index, simplye return the state, version of the backend api and link to the swagger
    """
    ret = {
        "state": "running",
        "version": __version__,
        "swagger": "blabla"
    }
    return ret


@click.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default="5000")
@click.option("--debug/--no-debug", default=True)
@click.option("--dev", is_flag=True)
@click.option("--ssl", is_flag=True)
def main(host: str, port: str, debug: bool, dev: bool, ssl: bool):
    """
    Main function starting the Flask application with passed arguments.
    """

    config.IS_DEV = dev

    # enable automatic request compression
    compress = Compress()
    compress.init_app(app)

    ssl_context = "adhoc" if ssl else None

    # List of arguments -> https://werkzeug.palletsprojects.com/en/stable/serving/#werkzeug.serving.run_simple
    app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
