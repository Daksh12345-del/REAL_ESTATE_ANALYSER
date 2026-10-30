from flask import Flask, jsonify
from flask_cors import CORS

from routes.api import ApiError, bp as api_bp
from routes.models_api import bp as models_bp
from routes.tools_api import bp as tools_bp


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(api_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(tools_bp)

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify({"error": e.message}), e.status

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(_):
        return jsonify({"error": "Server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)