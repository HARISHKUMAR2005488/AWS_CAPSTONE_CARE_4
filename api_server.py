"""Deployment entrypoint for the modular CARE_4_U API."""

from care4u_api import create_app

app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
