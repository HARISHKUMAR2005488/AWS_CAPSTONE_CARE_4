"""OpenAPI route registration (lightweight, no external framework)."""

from flask import jsonify


def register_openapi_routes(app):
    """Register basic OpenAPI docs endpoint."""

    @app.get('/api/v1/openapi.json')
    def openapi_spec():
        spec = {
            'openapi': '3.0.3',
            'info': {
                'title': 'CARE_4_U API',
                'version': '1.0.0',
            },
            'paths': {
                '/api/v1/auth/register': {'post': {'summary': 'Register user'}},
                '/api/v1/auth/login': {'post': {'summary': 'Login with email or phone'}},
                '/api/v1/appointments': {
                    'get': {'summary': 'List user appointments'},
                    'post': {'summary': 'Create appointment'},
                },
                '/api/v1/appointments/{appointment_id}': {
                    'put': {'summary': 'Update appointment'},
                    'delete': {'summary': 'Delete appointment'},
                },
                '/api/v1/notifications/publish': {'post': {'summary': 'Publish SNS notification'}},
                '/api/v1/chatbot/message': {'post': {'summary': 'Chatbot inference'}},
            },
        }
        return jsonify(spec)
